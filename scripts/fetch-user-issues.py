#!/usr/bin/env python3
"""Find issues assigned to or reported by a drupal.org user on a project.

Usage:
    python3 fetch-user-issues.py zorz ai_best_practices
    python3 fetch-user-issues.py zorz ai_best_practices --reported
    python3 fetch-user-issues.py zorz ai_best_practices --all
    python3 fetch-user-issues.py zorz ai_best_practices --json
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
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

API_BASE = "https://www.drupal.org/api-d7"


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


def resolve_uid(username):
    """Look up a drupal.org user ID from username."""
    data = fetch_json(f"{API_BASE}/user.json?name={urllib.request.quote(username)}")
    users = data.get("list", [])
    if not users:
        print(f"Error: user '{username}' not found on drupal.org", file=sys.stderr)
        sys.exit(1)
    return str(users[0].get("uid", ""))


def resolve_project_nid(machine_name):
    """Resolve a project machine name to its drupal.org node ID.

    Search for any node with this project machine name and extract the
    field_project reference. This works regardless of project type.
    """
    data = fetch_json(
        f"{API_BASE}/node.json?field_project_machine_name="
        f"{urllib.request.quote(machine_name)}&limit=1"
    )
    nodes = data.get("list", [])
    if not nodes:
        print(f"Error: project '{machine_name}' not found on drupal.org", file=sys.stderr)
        sys.exit(1)
    project_ref = nodes[0].get("field_project", {})
    project_nid = project_ref.get("id", "")
    if not project_nid:
        project_nid = nodes[0].get("nid", "")
    return str(project_nid)


def ts_to_date(timestamp):
    """Convert unix timestamp string to readable date."""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return timestamp


def fetch_json_safe(url):
    """Fetch JSON, returning None on 404 (used for pagination)."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"Error fetching {url}: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error fetching {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def fetch_all_pages(base_url):
    """Fetch all pages of a paginated drupal.org API response."""
    issues = []
    page = 0
    while True:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}page={page}"
        data = fetch_json_safe(url)
        if data is None:
            break
        page_list = data.get("list", [])
        if not page_list:
            break
        issues.extend(page_list)
        if not data.get("next"):
            break
        page += 1
        if page > 50:
            break
    return issues


def fetch_assigned_issues(uid, project_nid):
    """Fetch issues assigned to a user on a project."""
    url = (
        f"{API_BASE}/node.json?type=project_issue"
        f"&field_project={project_nid}"
        f"&field_issue_assigned={uid}"
        f"&sort=changed&direction=DESC"
    )
    return fetch_all_pages(url)


def fetch_reported_issues(uid, project_nid):
    """Fetch issues reported by a user on a project."""
    url = (
        f"{API_BASE}/node.json?type=project_issue"
        f"&field_project={project_nid}"
        f"&author={uid}"
        f"&sort=changed&direction=DESC"
    )
    return fetch_all_pages(url)


def parse_issue(node):
    """Extract relevant fields from a raw issue node."""
    status_code = str(node.get("field_issue_status", ""))
    return {
        "nid": node.get("nid", ""),
        "title": node.get("title", ""),
        "url": node.get("url", ""),
        "status": ISSUE_STATUSES.get(status_code, status_code),
        "component": node.get("field_issue_component", ""),
        "changed": ts_to_date(node.get("changed", "")),
        "comment_count": node.get("comment_count", 0),
    }


def dedup_issues(issues):
    """Remove duplicate issues by nid, preserving order."""
    seen = set()
    result = []
    for issue in issues:
        nid = issue["nid"]
        if nid not in seen:
            seen.add(nid)
            result.append(issue)
    return result


def print_section(label, issues):
    """Print a section of issues."""
    print(f"## {label} ({len(issues)})")
    if not issues:
        print("  (none)")
        print()
        return
    for issue in issues:
        print(f"  #{issue['nid']} [{issue['status']}] {issue['title']}")
        print(f"    Component: {issue['component']} | Updated: {issue['changed']} | Comments: {issue['comment_count']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Find drupal.org issues assigned to or reported by a user"
    )
    parser.add_argument("username", help="drupal.org username")
    parser.add_argument("project", help="Project machine name (e.g. ai_best_practices)")
    parser.add_argument(
        "--reported", action="store_true",
        help="Show issues reported by user (instead of assigned)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show both assigned and reported issues"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    # Resolve username to uid and project to node ID.
    uid = resolve_uid(args.username)
    project_nid = resolve_project_nid(args.project)

    # Determine which sets to fetch.
    show_assigned = not args.reported or args.all
    show_reported = args.reported or args.all

    assigned = []
    reported = []

    if show_assigned:
        raw = fetch_assigned_issues(uid, project_nid)
        assigned = dedup_issues([parse_issue(n) for n in raw])

    if show_reported:
        raw = fetch_reported_issues(uid, project_nid)
        reported = dedup_issues([parse_issue(n) for n in raw])

    if args.json:
        output = {
            "username": args.username,
            "uid": uid,
            "project": args.project,
        }
        if show_assigned:
            output["assigned"] = assigned
        if show_reported:
            output["reported"] = reported
        print(json.dumps(output, indent=2))
        return

    # Human-readable output.
    print(f"# {args.username} on {args.project}")
    print()

    if show_assigned:
        print_section("Assigned", assigned)

    if show_reported:
        print_section("Reported", reported)


if __name__ == "__main__":
    main()
