# drupalorg-claude-skill

A Claude Code skill for reading drupal.org issues, comments, merge requests, and user activity. Works with both the drupal.org REST API and git.drupalcode.org GitLab API.

## Why this exists

drupal.org returns 403 to direct page fetches, so Claude's WebFetch tool can't read issue pages. These scripts use the JSON API instead, giving Claude full access to the issue queue.

## What's included

| Script | What it does |
|--------|-------------|
| `fetch-issue.py` | Fetch an issue with all comments, decoded statuses, stripped HTML |
| `fetch-issues.py` | Search/list issues with status, category, component filters |
| `fetch-mr.py` | Fetch merge requests, branches, and issue fork detection from GitLab |
| `watch-issues.py` | Check multiple issues for changes since a given time |
| `fetch-user-issues.py` | Find issues assigned to or reported by a user |
| `format-comment.py` | Convert markdown to drupal.org HTML, optionally copy to clipboard |

## Installation

### As a Claude Code skill (recommended)

Copy the `skills/drupal-org-api/` directory into your project or user skills directory:

```bash
# Project-level (just this project)
mkdir -p .claude/skills
cp -r /path/to/drupalorg-claude-skill .claude/skills/drupal-org-api

# User-level (all projects)
mkdir -p ~/.claude/skills
cp -r /path/to/drupalorg-claude-skill ~/.claude/skills/drupal-org-api
```

Or clone directly:

```bash
git clone https://github.com/gkastanis/drupalorg-claude-skill.git ~/.claude/skills/drupal-org-api
```

### Standalone (without Claude Code)

The scripts work independently with Python 3.8+. No external dependencies.

```bash
python3 scripts/fetch-issue.py 3583213
python3 scripts/fetch-issues.py ai_best_practices --status active
python3 scripts/fetch-mr.py ai_best_practices --issue 3583213
```

## Usage examples

**Get the full picture on an issue:**
```bash
python3 scripts/fetch-issue.py 3583213
```

**List active issues for a project:**
```bash
python3 scripts/fetch-issues.py ai_best_practices --status active
python3 scripts/fetch-issues.py ai --status "needs review" --limit 20
```

**Check if anyone has started work:**
```bash
python3 scripts/fetch-mr.py ai_best_practices --issue 3583213
```

**What changed since yesterday?**
```bash
python3 scripts/watch-issues.py 3583213 3583241 3582953 --since 24h
```

**What am I working on?**
```bash
python3 scripts/fetch-user-issues.py zorz ai_best_practices
```

**Format a comment for drupal.org:**
```bash
echo "Some **markdown** with a [link](https://drupal.org)" | python3 scripts/format-comment.py --clip
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)
- `xclip` for clipboard support in `format-comment.py` (optional, Linux only)

## Related tools

- [drupalorg-cli](https://github.com/mglaman/drupalorg-cli) by mglaman - PHP CLI for drupal.org with MCP server support. Focuses on git workflow (issue forks, branch checkout, remotes). Complementary to this skill which focuses on reading issues and comments.
- [ai_best_practices](https://www.drupal.org/project/ai_best_practices) - Community-maintained Drupal best practice guidance for AI agents.

## License

GPL-2.0-or-later
