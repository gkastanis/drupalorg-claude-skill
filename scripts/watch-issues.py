#!/usr/bin/env python3
"""Watch multiple drupal.org issues for changes since a given time.

Usage:
    python3 watch-issues.py 3583213 3583241 3582953 --since 2026-04-06
    python3 watch-issues.py 3583213 3583241 --since "2026-04-06 14:00"
    python3 watch-issues.py 3583213 3583241 --since 24h
    python3 watch-issues.py 3583213 3583241 --since 7d
    python3 watch-issues.py 3583213 3583241 --json
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cache import cached_fetch_json
import urllib.error
from datetime import datetime, timedelta

ISSUE_STATUSES = {
    "1": "Active",
    "2": "Fixed",
    "3": "Closed (duplicate)",
    "4": "Postponed",
    "5": "Closed (won't fix)",
    "6": "Closed (works as designed)",
    "7": "Closed (fixed)",
    "8": "Needs review",
    "13": "Needs work",
    "14": "RTBC",
    "15": "Patch (to be ported)",
    "16": "Postponed (maintainer needs more info)",
    "18": "Closed (outdated)",
}


def fetch_json(url):
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error fetching {url}: HTTP {e.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Error fetching {url}: {e.reason}", file=sys.stderr)
        return None


def ts_to_date(timestamp):
    """Convert unix timestamp string to readable date."""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return timestamp


def ts_to_datetime(timestamp):
    """Convert unix timestamp string to datetime object."""
    try:
        return datetime.fromtimestamp(int(timestamp))
    except (ValueError, TypeError, OSError):
        return None


def strip_html(html):
    """Minimal HTML tag stripping for readable output."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<p>", "\n", text)
    text = re.sub(r"</p>", "", text)
    text = re.sub(r"<li>", "\n- ", text)
    text = re.sub(r"<pre><code[^>]*>", "\n```\n", text)
    text = re.sub(r"</code></pre>", "\n```\n", text)
    text = re.sub(r"<code[^>]*>", "`", text)
    text = re.sub(r"</code>", "`", text)
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', r"\2 (\1)", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text, max_len=100):
    """Truncate text to max_len chars, adding ellipsis if needed."""
    # Collapse to single line for summary display.
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len].rstrip() + "..."


def parse_since(since_str):
    """Parse --since value into a datetime.

    Accepts:
      - Relative: "24h", "48h", "7d"
      - Date only: "2026-04-06" (midnight)
      - Date+time: "2026-04-06 14:00"
    """
    if not since_str:
        return datetime.now() - timedelta(hours=24)

    # Relative: hours.
    match = re.match(r"^(\d+)h$", since_str)
    if match:
        return datetime.now() - timedelta(hours=int(match.group(1)))

    # Relative: days.
    match = re.match(r"^(\d+)d$", since_str)
    if match:
        return datetime.now() - timedelta(days=int(match.group(1)))

    # Date+time.
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(since_str, fmt)
        except ValueError:
            continue

    # Date only (midnight).
    try:
        return datetime.strptime(since_str, "%Y-%m-%d")
    except ValueError:
        pass

    print(f"Error: cannot parse --since '{since_str}'", file=sys.stderr)
    print("  Expected: YYYY-MM-DD, 'YYYY-MM-DD HH:MM', 24h, 7d", file=sys.stderr)
    sys.exit(1)


def fetch_issue_changes(nid, since_dt):
    """Fetch an issue and determine what changed since since_dt.

    Returns a dict with issue metadata, whether it changed, and new comments.
    """
    data = fetch_json(f"https://www.drupal.org/api-d7/node/{nid}.json")
    if data is None:
        return {
            "nid": nid,
            "error": True,
            "title": f"(failed to fetch #{nid})",
            "status": "unknown",
            "changed": False,
            "new_comments": [],
        }

    title = data.get("title", "")
    status_code = data.get("field_issue_status", "")
    status = ISSUE_STATUSES.get(status_code, status_code)
    changed_ts = data.get("changed", "")
    changed_dt = ts_to_datetime(changed_ts)

    issue_changed = changed_dt is not None and changed_dt > since_dt

    # Only fetch comments if the issue changed since our cutoff.
    new_comments = []
    if issue_changed:
        # Single request for all comments (tip from marcus_johansson).
        page = 0
        while True:
            comments_url = f"https://www.drupal.org/api-d7/comment.json?node={nid}&limit=100&page={page}"
            cpage = cached_fetch_json(comments_url, ttl=300)
            if cpage is None:
                break
            clist = cpage.get("list", [])
            if not clist:
                break

            for cdata in clist:
                comment_created = ts_to_datetime(cdata.get("created", ""))
                if comment_created is None or comment_created <= since_dt:
                    continue

                comment_body = cdata.get("comment_body", {})
                if isinstance(comment_body, list):
                    comment_body = comment_body[0] if comment_body else {}
                body_html = comment_body.get("value", "") if isinstance(comment_body, dict) else str(comment_body)

                if "created an issue" in body_html and len(body_html) < 200:
                    continue

                body_text = strip_html(body_html)
                new_comments.append({
                    "cid": cdata.get("cid", ""),
                    "author": cdata.get("name", "unknown"),
                    "created": ts_to_date(cdata.get("created", "")),
                    "body": body_text,
                    "snippet": truncate(body_text),
                })

            if not cpage.get("next"):
                break
            page += 1
            time.sleep(0.1)  # Rate limit between pages.

    return {
        "nid": nid,
        "error": False,
        "title": title,
        "status": status,
        "changed": issue_changed,
        "last_updated": ts_to_date(changed_ts),
        "new_comments": new_comments,
        "url": data.get("url", f"https://www.drupal.org/node/{nid}"),
    }


def print_results(results, since_dt):
    """Print results in readable format."""
    since_str = since_dt.strftime("%Y-%m-%d %H:%M")
    print(f"# Issue watch (since {since_str})")
    print()

    for r in results:
        if r.get("error"):
            print(f"## #{r['nid']}: (error fetching issue)")
            print(f"  Could not retrieve issue data.")
            print()
            continue

        print(f"## #{r['nid']}: {r['title']} [{r['status']}]")

        if not r["changed"]:
            print(f"  No changes since {since_str}")
            print()
            continue

        comments = r["new_comments"]
        if comments:
            count = len(comments)
            label = "comment" if count == 1 else "comments"
            print(f"  {count} new {label}:")
            for c in comments:
                print(f"    {c['author']} ({c['created']}): {c['snippet']}")
        else:
            print(f"  Updated (no new comments)")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Watch multiple drupal.org issues for changes"
    )
    parser.add_argument(
        "nids",
        nargs="+",
        help="Issue node IDs (e.g. 3583213 3583241)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "Check for changes since this time. "
            "Accepts: YYYY-MM-DD, 'YYYY-MM-DD HH:MM', 24h, 7d. "
            "Default: 24h"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON",
    )
    args = parser.parse_args()

    since_dt = parse_since(args.since)

    # Strip leading # if present.
    nids = [nid.lstrip("#") for nid in args.nids]

    results = []
    for nid in nids:
        results.append(fetch_issue_changes(nid, since_dt))

    if args.json:
        output = {
            "since": since_dt.strftime("%Y-%m-%d %H:%M"),
            "issues": results,
        }
        print(json.dumps(output, indent=2))
    else:
        print_results(results, since_dt)


if __name__ == "__main__":
    main()
