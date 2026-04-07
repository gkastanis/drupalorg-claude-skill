---
name: drupal-org-api
description: Fetch issues, comments, merge requests, and user activity from drupal.org and git.drupalcode.org. Use this skill when you need structured or filtered data from the drupal.org issue queue - listing issues by status, watching multiple issues for changes, checking MRs/branches on GitLab, looking up user assignments, or formatting comments. Also use for JSON output or when you need to process issue data programmatically. For simply reading a single issue page, WebFetch now works (claudebot was unblocked April 2026).
---

# Drupal.org API

These scripts provide structured, cached, rate-limited access to the drupal.org JSON API and git.drupalcode.org GitLab API. For reading a single issue page, WebFetch works too (claudebot unblocked April 2026). Use these scripts when you need filtering, JSON output, multi-issue watching, or GitLab data.

## Fetch an issue with all comments

```bash
python3 SKILL_DIR/scripts/fetch-issue.py <issue-number>
python3 SKILL_DIR/scripts/fetch-issue.py 3583213 --comments-only
python3 SKILL_DIR/scripts/fetch-issue.py 3583213 --json
```

Resolves author names, converts timestamps, strips HTML to readable text, skips auto-generated comments. Decodes status codes (1=Active, 2=Fixed, 8=Needs review, 13=Needs work, 14=RTBC).

## List/search issues for a project

```bash
python3 SKILL_DIR/scripts/fetch-issues.py <project-name>
python3 SKILL_DIR/scripts/fetch-issues.py ai_best_practices --status active
python3 SKILL_DIR/scripts/fetch-issues.py ai_best_practices --status "needs review"
python3 SKILL_DIR/scripts/fetch-issues.py ai_best_practices --limit 20
python3 SKILL_DIR/scripts/fetch-issues.py ai_best_practices --json
```

The `--status` flag accepts human-readable names: active, fixed, "needs review", "needs work", rtbc.

## Fetch merge requests and branches

```bash
python3 SKILL_DIR/scripts/fetch-mr.py <project-name>
python3 SKILL_DIR/scripts/fetch-mr.py ai_best_practices --issue 3583213
python3 SKILL_DIR/scripts/fetch-mr.py ai_best_practices --json
```

Automatically finds the GitLab project ID, checks for issue fork repos, and filters by issue number. To check if anyone has started work on an issue, run this with `--issue` and look for branches, MRs, or an issue fork.

## Watch multiple issues for changes

```bash
python3 SKILL_DIR/scripts/watch-issues.py 3583213 3583241 3582953
python3 SKILL_DIR/scripts/watch-issues.py 3583213 3583241 --since 2026-04-06
python3 SKILL_DIR/scripts/watch-issues.py 3583213 --since 24h
python3 SKILL_DIR/scripts/watch-issues.py 3583213 --json
```

Shows only new comments since the given time. Default is 24 hours. Accepts dates (`2026-04-06`), datetimes (`2026-04-06 14:00`), or relative (`24h`, `7d`).

## Look up a user's issues

```bash
python3 SKILL_DIR/scripts/fetch-user-issues.py <username> <project-name>
python3 SKILL_DIR/scripts/fetch-user-issues.py zorz ai_best_practices
python3 SKILL_DIR/scripts/fetch-user-issues.py zorz ai_best_practices --reported
python3 SKILL_DIR/scripts/fetch-user-issues.py zorz ai_best_practices --all
```

Default shows assigned issues. Use `--reported` for authored issues, `--all` for both.

## Format a comment for drupal.org

```bash
echo "Some **bold** markdown" | python3 SKILL_DIR/scripts/format-comment.py
python3 SKILL_DIR/scripts/format-comment.py comment.md
python3 SKILL_DIR/scripts/format-comment.py comment.md --clip
```

Converts markdown to drupal.org-compatible HTML. The `--clip` flag copies to clipboard via xclip (in addition to printing). Handles headings (# maps to h2), bold, italic, links, code blocks, lists, blockquotes, and horizontal rules. Preserves underscores inside URLs and code.

## Common workflows

**"What's happening on issue X?"**
```bash
python3 SKILL_DIR/scripts/fetch-issue.py <number>
```

**"Has anyone started work on issue X?"**
```bash
python3 SKILL_DIR/scripts/fetch-mr.py <project> --issue <number>
```

**"What changed since yesterday?"**
```bash
python3 SKILL_DIR/scripts/watch-issues.py <nid1> <nid2> <nid3> --since 24h
```

**"What am I working on?"**
```bash
python3 SKILL_DIR/scripts/fetch-user-issues.py <username> <project>
```

**"Write a comment and copy to clipboard"**
```bash
echo "your markdown here" | python3 SKILL_DIR/scripts/format-comment.py --clip
```

## API notes

- drupal.org uses a Drupal 7 REST API at `/api-d7/`. Node IDs are issue numbers.
- git.drupalcode.org is a GitLab instance. Projects live under `project/` namespace.
- Issue fork repos are separate GitLab projects. They show up in project search results.
- No authentication needed for read-only access.
- Comments are fetched individually by ID (the issue JSON only has references, not bodies).
- The project machine name is in the URL: `drupal.org/project/ai_best_practices/issues/123` means project is `ai_best_practices`.
