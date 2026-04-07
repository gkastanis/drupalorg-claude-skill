#!/usr/bin/env python3
"""Search and list issues for a drupal.org project.

Usage:
    python3 fetch-issues.py ai_best_practices
    python3 fetch-issues.py ai_best_practices --status active
    python3 fetch-issues.py ai_best_practices --status "needs review"
    python3 fetch-issues.py ai_best_practices --category bug
    python3 fetch-issues.py ai_best_practices --component Evals
    python3 fetch-issues.py ai_best_practices --limit 20
    python3 fetch-issues.py ai_best_practices --json
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

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

# Reverse map: human-readable name (lowercased) -> API status code.
STATUS_NAMES = {v.lower(): k for k, v in ISSUE_STATUSES.items()}
# Convenience aliases for common statuses.
STATUS_NAMES.update({
    "active": "1",
    "fixed": "2",
    "postponed": "4",
    "needs review": "8",
    "needs work": "13",
    "rtbc": "14",
    "closed": "7",
})

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

# Reverse map: human-readable name (lowercased) -> API category code.
CATEGORY_NAMES = {v.lower(): k for k, v in CATEGORIES.items()}
# Convenience aliases.
CATEGORY_NAMES.update({
    "bug": "1",
    "task": "2",
    "feature": "3",
    "support": "4",
    "plan": "5",
})

API_BASE = "https://www.drupal.org/api-d7/node.json"


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
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
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


def resolve_status(name):
    """Resolve a human-readable status name to its API code."""
    key = name.lower().strip()
    code = STATUS_NAMES.get(key)
    if code:
        return code
    # Partial match fallback.
    for label, c in STATUS_NAMES.items():
        if key in label:
            return c
    print(f"Error: unknown status '{name}'", file=sys.stderr)
    print(f"Valid statuses: {', '.join(sorted(set(STATUS_NAMES.keys())))}", file=sys.stderr)
    sys.exit(1)


def resolve_category(name):
    """Resolve a human-readable category name to its API code."""
    key = name.lower().strip()
    code = CATEGORY_NAMES.get(key)
    if code:
        return code
    for label, c in CATEGORY_NAMES.items():
        if key in label:
            return c
    print(f"Error: unknown category '{name}'", file=sys.stderr)
    print(f"Valid categories: {', '.join(sorted(set(CATEGORY_NAMES.keys())))}", file=sys.stderr)
    sys.exit(1)


def resolve_project_nid(machine_name):
    """Resolve a project machine name to its drupal.org node ID.

    The issue search API requires field_project={nid}, not machine_name.
    We look up the project node first using field_project_machine_name.
    """
    data = fetch_json(
        f"{API_BASE}?field_project_machine_name={urllib.parse.quote(machine_name)}&limit=1"
    )
    nodes = data.get("list", [])
    if not nodes:
        print(f"Error: project '{machine_name}' not found on drupal.org", file=sys.stderr)
        sys.exit(1)
    # The project node is referenced in field_project of any result,
    # but the simplest path: search for project nodes directly.
    project_ref = nodes[0].get("field_project", {})
    project_nid = project_ref.get("id", "")
    if not project_nid:
        # Fallback: the result itself might be the project node.
        project_nid = nodes[0].get("nid", "")
    return project_nid


def fetch_issues(project, limit=10, status=None, category=None,
                 component=None, assigned=None):
    """Fetch issues for a drupal.org project."""
    project_nid = resolve_project_nid(project)

    params = {
        "type": "project_issue",
        "field_project": project_nid,
        "limit": str(limit),
        "sort": "changed",
        "direction": "DESC",
    }
    if status:
        params["field_issue_status"] = resolve_status(status)
    if category:
        params["field_issue_category"] = resolve_category(category)
    if component:
        params["field_issue_component"] = component
    if assigned:
        params["field_issue_assigned"] = assigned

    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)

    nodes = data.get("list", [])
    if not nodes:
        return []

    # Collect unique author IDs to batch-resolve usernames.
    author_ids = set()
    assignee_ids = set()
    for node in nodes:
        aid = node.get("author", {}).get("id", "")
        if aid:
            author_ids.add(aid)
        # Assigned is a user reference; id=0 means unassigned.
        assigned_ref = node.get("field_issue_assigned", {})
        if isinstance(assigned_ref, dict):
            auid = assigned_ref.get("id", "")
            if auid and str(auid) != "0":
                assignee_ids.add(str(auid))

    # Resolve all unique user IDs.
    user_cache = {}
    for uid in author_ids | assignee_ids:
        user_cache[str(uid)] = fetch_user(uid)

    issues = []
    for node in nodes:
        nid = node.get("nid", "")
        aid = str(node.get("author", {}).get("id", ""))
        reporter = user_cache.get(aid, "unknown")

        # Resolve assignee.
        assignee = None
        assigned_ref = node.get("field_issue_assigned", {})
        if isinstance(assigned_ref, dict):
            auid = str(assigned_ref.get("id", ""))
            if auid and auid != "0":
                assignee = user_cache.get(auid)

        issues.append({
            "nid": nid,
            "title": node.get("title", ""),
            "url": node.get("url", f"https://www.drupal.org/node/{nid}"),
            "status": ISSUE_STATUSES.get(
                node.get("field_issue_status", ""),
                node.get("field_issue_status", ""),
            ),
            "priority": PRIORITIES.get(
                node.get("field_issue_priority", ""),
                node.get("field_issue_priority", ""),
            ),
            "category": CATEGORIES.get(
                node.get("field_issue_category", ""),
                node.get("field_issue_category", ""),
            ),
            "component": node.get("field_issue_component", ""),
            "reporter": reporter,
            "assignee": assignee,
            "comment_count": node.get("comment_count", 0),
            "changed": ts_to_date(node.get("changed", "")),
        })

    return issues


def print_issues(project, issues, status_filter=None):
    """Print issues in readable format."""
    label = status_filter.capitalize() if status_filter else "Recent"
    print(f"# {project} - {label} issues")
    print()

    if not issues:
        print("No issues found.")
        return

    for issue in issues:
        print(f"#{issue['nid']} [{issue['status']}] {issue['title']}")
        line2_parts = [f"Reporter: {issue['reporter']}"]
        if issue["assignee"]:
            line2_parts.append(f"Assigned: {issue['assignee']}")
        line2_parts.append(f"Component: {issue['component']}")
        line2_parts.append(f"Comments: {issue['comment_count']}")
        print(f"  {' | '.join(line2_parts)}")
        print(f"  Updated: {issue['changed']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Search and list issues for a drupal.org project"
    )
    parser.add_argument("project", help="Project machine name (e.g. ai_best_practices)")
    parser.add_argument("--status", default=None,
                        help="Filter by status (active, fixed, 'needs review', 'needs work', rtbc)")
    parser.add_argument("--category", default=None,
                        help="Filter by category (bug, task, feature, support, plan)")
    parser.add_argument("--component", default=None,
                        help="Filter by component name")
    parser.add_argument("--assigned", default=None,
                        help="Filter by assignee user ID")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of issues to fetch (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    issues = fetch_issues(
        project=args.project,
        limit=args.limit,
        status=args.status,
        category=args.category,
        component=args.component,
        assigned=args.assigned,
    )

    if args.json:
        print(json.dumps({
            "project": args.project,
            "status_filter": args.status,
            "category_filter": args.category,
            "component_filter": args.component,
            "count": len(issues),
            "issues": issues,
        }, indent=2))
    else:
        print_issues(args.project, issues, status_filter=args.status)


if __name__ == "__main__":
    main()
