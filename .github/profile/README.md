# Profile activity card

The profile README displays aggregate WakaTime activity for the seven complete days before today, using Asia/Shanghai dates. The SVG has desktop and mobile layouts. Daily totals come from the official summaries API, and language shares are calculated from summed language durations over the same date range. This measures recorded editor and AI coding activity, not Codex token usage or subscription allowance. Recently installed trackers cannot reconstruct every untracked activity.

Run `python3 .github/profile/update_wakatime.py` to render locally, or add `--publish` to publish. The script reads the existing API key from `~/.wakatime.cfg`; the key is never included in generated files or GitHub settings. The WakaTime account can remain private.

Only `wakatime.json`, `wakatime.svg`, and `wakatime-mobile.svg` are published by the daily updater. The JSON contains dates, durations, active-day counts and language aggregates. It excludes credentials, account identifiers, projects, paths, machines and conversation content. Missing or invalid data causes the update to stop. Publishing uses the latest remote tree, a non-forced commit, `[skip deploy]`, and a read-back check.

The local Codex daily automation runs at 09:00 Asia/Shanghai. The Mac must be online with the WakaTime configuration and GitHub CLI authentication available. Old Codex assets and their updater remain as a rollback reference; the daily job no longer calls that updater.

GitHub's native repository and pinned-repository sections are controlled by GitHub and cannot be removed by this README.

## Codex token city

The second card shows a 13-week calendar of recorded Codex token usage. Run `python3 .github/profile/update_codex_city.py` to read the existing local Codex login and render both sizes; add `--publish` to update only `codex-city.json`, `codex-city.svg`, and `codex-city-mobile.svg`. The updater makes no model inference calls and does not read or reset quota limits. It is separate from the retired flat-card `update_profile.py`.

Daily values come from the official app-server `account/usage/read` response's `dailyUsageBuckets`, using `startDate` without timezone conversion. The service does not provide an input/output/cache breakdown in these buckets. The card labels these as recorded tokens and does not claim complete coverage of all devices. Missing dates remain unknown; returned zero values are shown separately. Height uses a square-root scale relative to the displayed peak, and color increases with usage. The seven-day statistic ends at the latest returned date; an incomplete seven-day window is labeled with its returned-day count.

Only dates, token counts, coverage and the collection timestamp are exported. Thread metadata, messages, project names, machine details, account identifiers, credentials and quota data are excluded. Empty, malformed, duplicate, future or stale buckets stop publication. The publisher updates an explicit three-file allowlist, preserves the latest remote tree, rejects concurrent non-fast-forward changes and reads all three files back after publishing.

The automatic refresh runs from the signed-in Mac because GitHub Actions does not have this Codex account's local login. The Mac must be online. GitHub contribution-city generation remains available as a manual workflow.
