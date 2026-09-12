# Profile activity card

The profile README displays aggregate WakaTime activity for the seven complete days before today, using Asia/Shanghai dates. The SVG has desktop and mobile layouts. Daily totals come from the official summaries API, and language shares are calculated from summed language durations over the same date range. This measures recorded editor and AI coding activity, not Codex token usage or subscription allowance. Recently installed trackers cannot reconstruct every untracked activity.

Run `python3 .github/profile/update_wakatime.py` to render locally, or add `--publish` to publish. The script reads the existing API key from `~/.wakatime.cfg`; the key is never included in generated files or GitHub settings. The WakaTime account can remain private.

Only `wakatime.json`, `wakatime.svg`, and `wakatime-mobile.svg` are published by the daily updater. The JSON contains dates, durations, active-day counts and language aggregates. It excludes credentials, account identifiers, projects, paths, machines and conversation content. Missing or invalid data causes the update to stop. Publishing uses the latest remote tree, a non-forced commit, `[skip deploy]`, and a read-back check.

The local Codex daily automation runs at 09:00 Asia/Shanghai. The Mac must be online with the WakaTime configuration and GitHub CLI authentication available. Old Codex assets and their updater remain as a rollback reference; the daily job no longer calls that updater.

GitHub's native repository and pinned-repository sections are controlled by GitHub and cannot be removed by this README.
