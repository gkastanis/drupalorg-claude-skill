#!/usr/bin/env python3
"""Convert markdown to drupal.org HTML format and optionally copy to clipboard.

Usage:
    echo "Some **bold** text" | python3 format-comment.py
    python3 format-comment.py comment.md
    echo "Some text" | python3 format-comment.py --clip
    python3 format-comment.py comment.md --clip

Drupal.org allowed HTML tags:
    h2, h3, h4, h5, h6, em, strong, pre, code, del, blockquote,
    p, br, ul, ol, li, a, table, tr, td, th, thead, tbody, hr
"""

import argparse
import re
import shutil
import subprocess
import sys


def convert_inline(text):
    """Convert inline markdown elements to HTML."""
    # Extract code spans to placeholders so bold/italic don't corrupt them.
    code_spans = []
    def _save_code(m):
        code_spans.append(m.group(1))
        return f"\x00CODE{len(code_spans) - 1}\x00"
    text = re.sub(r'`([^`]+)`', _save_code, text)
    # Bold before italic to handle ** vs * correctly.
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\w)__(.+?)__(?!\w)', r'<strong>\1</strong>', text)
    # Italic.
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)
    # Strikethrough.
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    # Links.
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Restore code spans.
    for i, code in enumerate(code_spans):
        text = text.replace(f"\x00CODE{i}\x00", f"<code>{code}</code>")
    return text


def convert_markdown(md):
    """Convert markdown text to drupal.org-compatible HTML."""
    lines = md.split('\n')
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block.
        if line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            # Skip closing ```.
            i += 1
            code_content = '\n'.join(code_lines)
            output.append(f'<pre><code>{code_content}</code></pre>')
            continue

        # Horizontal rule.
        if re.match(r'^---+\s*$', line.strip()):
            output.append('<hr />')
            i += 1
            continue

        # Headings (# -> h2, ## -> h3, etc.).
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1)) + 1  # # -> h2
            if level > 6:
                level = 6
            text = convert_inline(heading_match.group(2))
            output.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # Blockquote.
        if line.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                # Strip the > prefix and optional space.
                content = re.sub(r'^>\s?', '', lines[i])
                quote_lines.append(content)
                i += 1
            quote_text = convert_inline(' '.join(quote_lines))
            output.append(f'<blockquote>{quote_text}</blockquote>')
            continue

        # Unordered list.
        if re.match(r'^[\s]*[-*]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[\s]*[-*]\s+', lines[i]):
                item_text = re.sub(r'^[\s]*[-*]\s+', '', lines[i])
                items.append(f'<li>{convert_inline(item_text)}</li>')
                i += 1
            output.append('<ul>' + ''.join(items) + '</ul>')
            continue

        # Ordered list.
        if re.match(r'^[\s]*\d+\.\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[\s]*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^[\s]*\d+\.\s+', '', lines[i])
                items.append(f'<li>{convert_inline(item_text)}</li>')
                i += 1
            output.append('<ol>' + ''.join(items) + '</ol>')
            continue

        # Blank line (paragraph separator).
        if line.strip() == '':
            i += 1
            continue

        # Paragraph: collect consecutive non-blank, non-special lines.
        para_lines = []
        while i < len(lines):
            current = lines[i]
            # Stop on blank line or start of a block element.
            if current.strip() == '':
                break
            if current.strip().startswith('```'):
                break
            if re.match(r'^#{1,6}\s+', current):
                break
            if current.startswith('>'):
                break
            if re.match(r'^[\s]*[-*]\s+', current):
                break
            if re.match(r'^[\s]*\d+\.\s+', current):
                break
            if re.match(r'^---+\s*$', current.strip()):
                break
            para_lines.append(current)
            i += 1
        para_text = convert_inline('<br />\n'.join(para_lines))
        output.append(f'<p>{para_text}</p>')
        continue

    return '\n'.join(output)


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip. Return True on success."""
    if not shutil.which('xclip'):
        print(
            'Warning: xclip not found. Install with: sudo apt install xclip',
            file=sys.stderr,
        )
        return False
    try:
        subprocess.run(
            ['xclip', '-selection', 'clipboard'],
            input=text.encode(),
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        print('Warning: failed to copy to clipboard.', file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown to drupal.org HTML format.',
    )
    parser.add_argument(
        'file',
        nargs='?',
        help='Markdown file to convert (reads stdin if omitted).',
    )
    parser.add_argument(
        '--clip',
        action='store_true',
        help='Also copy output to clipboard.',
    )
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r') as f:
                md_text = f.read()
        except FileNotFoundError:
            print(f'Error: file not found: {args.file}', file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f'Error reading file: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            print('Error: no input. Pipe markdown or pass a file.', file=sys.stderr)
            sys.exit(1)
        md_text = sys.stdin.read()

    html = convert_markdown(md_text)
    print(html)

    if args.clip:
        if copy_to_clipboard(html):
            print('Copied to clipboard.', file=sys.stderr)


if __name__ == '__main__':
    main()
