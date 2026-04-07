# drupalorg-claude-skill

A Claude Code skill for working with the drupal.org issue queue. Install it and ask Claude about any drupal.org issue, merge request, or contributor activity.

## Install

```bash
git clone https://github.com/gkastanis/drupalorg-claude-skill.git ~/.claude/skills/drupal-org-api
```

That's it. Claude will pick up the skill automatically.

## What you can ask

- "What's happening on issue #3583213?"
- "Has anyone started work on #3583213?"
- "Show me active issues on ai_best_practices"
- "What changed on #3583213 and #3583241 since yesterday?"
- "What issues is zorz assigned to on ai_best_practices?"
- "Write a comment about X and copy it to my clipboard"

## Why this exists

drupal.org returns 403 to direct page fetches, so Claude can't read issue pages with its built-in tools. This skill provides scripts that use the drupal.org JSON API and git.drupalcode.org GitLab API instead. No external dependencies, just Python 3.8+.

## Related tools

- [drupalorg-cli](https://github.com/mglaman/drupalorg-cli) by mglaman - Complementary PHP CLI focused on git workflow (issue forks, branch checkout). This skill focuses on reading issues and comments.

## License

GPL-2.0-or-later
