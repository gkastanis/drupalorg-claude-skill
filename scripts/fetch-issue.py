#!/usr/bin/env python3
"""Fetch a drupal.org issue with all its comments.

Usage:
    python3 fetch-issue.py 3583213
    python3 fetch-issue.py 3583213 --json
    python3 fetch-issue.py 3583213 --comments-only
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cache import cached_fetch_json

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

PRIORITIES = {
    "100": "Critical",
    "200": "Major",
    "300": "Normal",
    "400": "Minor",
}

CATEGORIES = {
    "1": "Bug report",
    "2": "Task",
    "3": "Feature request",
    "4": "Support request",
    "5": "Plan",
}


def fetch_json(url):
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error fetching {url}: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error fetching {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def fetch_user(user_id):
    """Fetch a drupal.org username by user ID."""
    data = fetch_json(f"https://www.drupal.org/api-d7/user/{user_id}.json")
    return data.get("name", f"uid:{user_id}")


def ts_to_date(timestamp):
    """Convert unix timestamp string to readable date."""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return timestamp


def strip_html(html):
    """Minimal HTML tag stripping for readable output."""
    import re
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


def fetch_issue(nid, comments_only=False):
    """Fetch issue and all comments."""
    data = fetch_json(f"https://www.drupal.org/api-d7/node/{nid}.json")

    # Resolve author.
    author_id = data.get("author", {}).get("id", "")
    author = fetch_user(author_id) if author_id else "unknown"

    issue = {
        "nid": nid,
        "title": data.get("title", ""),
        "url": data.get("url", f"https://www.drupal.org/node/{nid}"),
        "status": ISSUE_STATUSES.get(data.get("field_issue_status", ""), data.get("field_issue_status", "")),
        "priority": PRIORITIES.get(data.get("field_issue_priority", ""), data.get("field_issue_priority", "")),
        "category": CATEGORIES.get(data.get("field_issue_category", ""), data.get("field_issue_category", "")),
        "component": data.get("field_issue_component", ""),
        "version": data.get("field_issue_version", ""),
        "author": author,
        "created": ts_to_date(data.get("created", "")),
        "changed": ts_to_date(data.get("changed", "")),
        "comment_count": data.get("comment_count", 0),
        "body": strip_html(data.get("body", {}).get("value", "")),
        "project": data.get("field_project", {}).get("machine_name", ""),
    }

    # Fetch all comments in a single request (tip from marcus_johansson).
    comments = []
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
            comment_body = cdata.get("comment_body", {})
            if isinstance(comment_body, list):
                comment_body = comment_body[0] if comment_body else {}
            body_html = comment_body.get("value", "") if isinstance(comment_body, dict) else str(comment_body)

            # Skip auto-generated "created an issue" comments.
            if "created an issue" in body_html and len(body_html) < 200:
                continue

            comments.append({
                "cid": cdata.get("cid", ""),
                "author": cdata.get("name", "unknown"),
                "created": ts_to_date(cdata.get("created", "")),
                "body": strip_html(body_html),
            })

        if not cpage.get("next"):
            break
        page += 1
        time.sleep(0.1)  # Rate limit between pages.

    issue["comments"] = comments
    return issue


def print_issue(issue):
    """Print issue in readable format."""
    print(f"# {issue['title']}")
    print(f"  {issue['url']}")
    print(f"  Status: {issue['status']} | Priority: {issue['priority']} | Category: {issue['category']}")
    print(f"  Component: {issue['component']} | Version: {issue['version']}")
    print(f"  Reporter: {issue['author']} | Created: {issue['created']} | Updated: {issue['changed']}")
    print(f"  Project: {issue['project']}")
    print()

    if issue["body"]:
        print("## Issue body")
        print(issue["body"])
        print()

    if issue["comments"]:
        print(f"## Comments ({len(issue['comments'])})")
        print()
        for c in issue["comments"]:
            print(f"### {c['author']} ({c['created']})")
            print(c["body"])
            print()


def main():
    parser = argparse.ArgumentParser(description="Fetch a drupal.org issue with comments")
    parser.add_argument("nid", help="Issue node ID (e.g. 3583213)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--comments-only", action="store_true", help="Only show comments")
    args = parser.parse_args()

    # Strip leading # if present.
    nid = args.nid.lstrip("#")

    issue = fetch_issue(nid, comments_only=args.comments_only)

    if args.json:
        print(json.dumps(issue, indent=2))
    elif args.comments_only:
        for c in issue["comments"]:
            print(f"### {c['author']} ({c['created']})")
            print(c["body"])
            print()
    else:
        print_issue(issue)


if __name__ == "__main__":
    main()
