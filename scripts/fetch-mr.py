#!/usr/bin/env python3
"""Fetch merge requests and branches for a drupal.org project or issue.

Usage:
    python3 fetch-mr.py ai_best_practices
    python3 fetch-mr.py ai_best_practices --issue 3583213
    python3 fetch-mr.py ai_best_practices --json
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
import urllib.error

GITLAB_API = "https://git.drupalcode.org/api/v4"


def fetch_json(url):
    """Fetch JSON from a URL."""
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


def find_project_id(project_name):
    """Find the GitLab project ID for a drupal.org project.

    drupal.org projects live under the 'project/' namespace on git.drupalcode.org.
    The API search returns multiple results (including issue forks), so we match
    on the exact path.
    """
    data = fetch_json(f"{GITLAB_API}/projects?search={urllib.parse.quote(project_name)}&per_page=20")
    if not data:
        return None

    # Exact match on path_with_namespace.
    for project in data:
        if project.get("path_with_namespace") == f"project/{project_name}":
            return project["id"]

    # Fallback: first result with matching path.
    for project in data:
        if project.get("path") == project_name:
            return project["id"]

    return None


def fetch_mrs(project_id, issue_nid=None):
    """Fetch merge requests, optionally filtered by issue number in branch name."""
    data = fetch_json(
        f"{GITLAB_API}/projects/{project_id}/merge_requests"
        f"?state=all&per_page=30&order_by=created_at&sort=desc"
    )
    if not data:
        return []

    mrs = []
    for mr in data:
        entry = {
            "iid": mr.get("iid"),
            "title": mr.get("title", ""),
            "author": mr.get("author", {}).get("username", "unknown"),
            "state": mr.get("state", ""),
            "source_branch": mr.get("source_branch", ""),
            "target_branch": mr.get("target_branch", ""),
            "created_at": (mr.get("created_at") or "")[:10],
            "updated_at": (mr.get("updated_at") or "")[:10],
            "web_url": mr.get("web_url", ""),
        }
        mrs.append(entry)

    if issue_nid:
        nid = str(issue_nid)
        mrs = [m for m in mrs if nid in m["source_branch"] or nid in m["title"]]

    return mrs


def fetch_branches(project_id, issue_nid=None):
    """Fetch branches, optionally filtered by issue number."""
    data = fetch_json(f"{GITLAB_API}/projects/{project_id}/repository/branches?per_page=50")
    if not data:
        return []

    branches = []
    for b in data:
        commit = b.get("commit", {})
        entry = {
            "name": b.get("name", ""),
            "last_commit_author": commit.get("author_name", "unknown"),
            "last_commit_date": (commit.get("committed_date") or "")[:10],
            "last_commit_message": commit.get("title", ""),
        }
        branches.append(entry)

    if issue_nid:
        nid = str(issue_nid)
        branches = [b for b in branches if nid in b["name"]]

    return branches


def check_issue_fork(project_name, issue_nid):
    """Check if an issue fork repo exists for a specific issue."""
    data = fetch_json(f"{GITLAB_API}/projects?search={urllib.parse.quote(str(issue_nid))}&per_page=5")
    if not data:
        return None

    for project in data:
        path = project.get("path_with_namespace", "")
        if str(issue_nid) in path and project_name in path:
            return {
                "id": project["id"],
                "path": path,
                "web_url": project.get("web_url", ""),
                "last_activity": (project.get("last_activity_at") or "")[:10],
            }
    return None


def print_results(project_name, mrs, branches, issue_fork, issue_nid):
    """Print results in readable format."""
    context = f" for #{issue_nid}" if issue_nid else ""
    print(f"# {project_name}{context}")
    print()

    if issue_nid and issue_fork:
        print(f"## Issue fork")
        print(f"  {issue_fork['web_url']}")
        print(f"  Last activity: {issue_fork['last_activity']}")
        print()
    elif issue_nid:
        print(f"## Issue fork: none found")
        print()

    if mrs:
        print(f"## Merge requests ({len(mrs)})")
        for mr in mrs:
            state_icon = {"opened": "O", "merged": "M", "closed": "X"}.get(mr["state"], "?")
            print(f"  [{state_icon}] !{mr['iid']}: {mr['title']}")
            print(f"      Author: {mr['author']} | {mr['source_branch']} -> {mr['target_branch']}")
            print(f"      Created: {mr['created_at']} | Updated: {mr['updated_at']}")
            if mr["web_url"]:
                print(f"      {mr['web_url']}")
            print()
    else:
        print(f"## Merge requests: none{context}")
        print()

    if branches:
        print(f"## Branches ({len(branches)})")
        for b in branches:
            print(f"  {b['name']}")
            print(f"      {b['last_commit_author']} | {b['last_commit_date']} | {b['last_commit_message']}")
    elif issue_nid:
        print(f"## Branches: none matching #{issue_nid}")


def main():
    parser = argparse.ArgumentParser(description="Fetch MRs and branches from git.drupalcode.org")
    parser.add_argument("project", help="Project machine name (e.g. ai_best_practices)")
    parser.add_argument("--issue", default=None, help="Filter by issue number (e.g. 3583213)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    project_id = find_project_id(args.project)
    if not project_id:
        print(f"Error: project '{args.project}' not found on git.drupalcode.org", file=sys.stderr)
        sys.exit(1)

    issue_nid = args.issue.lstrip("#") if args.issue else None

    mrs = fetch_mrs(project_id, issue_nid)
    branches = fetch_branches(project_id, issue_nid)
    issue_fork = check_issue_fork(args.project, issue_nid) if issue_nid else None

    if args.json:
        print(json.dumps({
            "project": args.project,
            "project_id": project_id,
            "issue": issue_nid,
            "issue_fork": issue_fork,
            "merge_requests": mrs,
            "branches": branches,
        }, indent=2))
    else:
        print_results(args.project, mrs, branches, issue_fork, issue_nid)


if __name__ == "__main__":
    main()
