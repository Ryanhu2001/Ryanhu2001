# Codex profile card

Ryan's GitHub profile uses the generated desktop and mobile SVG cards in this directory.

The updater reads `account/usage/read` and `account/rateLimits/read` from the locally installed Codex app-server. It needs Python 3, a ChatGPT-backed Codex login and an authenticated GitHub CLI. It does not start a conversation or consume a reset.

```sh
python3 .github/profile/update_profile.py
python3 .github/profile/update_profile.py --publish
```

The first command generates a local preview. The second publishes only `stats.json`, `codex.svg` and `codex-mobile.svg` to `Ryanhu2001/Ryanhu2001` using one non-forced commit based on the latest default branch. Concurrent edits cause a safe failure instead of an overwrite. Other repository files and the blog are not modified. Refresh commits contain `[skip deploy]` to avoid a blog rebuild.

Only aggregate token counts, daily totals, streaks, quota percentages, reset times and snapshot dates are published. Credentials, account identifiers, conversations, project names, raw session files and credit information are never included in the public payload.

The lifetime count and streaks are the account service's reported values. The seven-day count ends on the latest returned daily bucket, which can lag behind today; its cutoff is printed on the card. Heatmap cells before the returned history and after the latest bucket are unknown, not zero. Missing dates within that range mean no recorded usage. A daily refresh is a snapshot, not a live quota display. Unavailable or expired quota windows are labelled unavailable. Missing core usage keeps the previous published card.

The Codex task schedules a daily refresh at 09:00 Asia/Shanghai on Ryan's Mac. The Mac and Codex scheduler must be available and both accounts must remain signed in. GitHub's image cache can delay visible updates.

Official protocol reference: https://learn.chatgpt.com/docs/app-server
