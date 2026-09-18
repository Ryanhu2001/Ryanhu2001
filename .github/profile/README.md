# Profile activity visuals

The profile displays exactly two visuals: a mint Codex NightView calendar followed
by a GitHub contribution snake. WakaTime and the older flat Codex card are no longer
displayed. Their files remain as rollback references; WakaTime's daily job is paused.

## Codex NightView

The projection, logarithmic columns and face shading adapt the NightView renderer
from [github-profile-3d-contrib v0.9.3](https://github.com/yoshi389111/github-profile-3d-contrib).
See `codex-city-NOTICE.md` for attribution and the MIT license. The palette is mint
on the original midnight background. The GitHub-specific language and repository
panels are replaced with actual daily-token and recent-token-share charts.

Desktop shows a 53-week calendar; mobile uses 13 weeks for readability. Headline
totals cover all returned records. Each bar represents a returned daily token value,
with the upstream logarithmic mapping applied in millions of tokens. A shared fit
factor keeps larger future peaks within the canvas. Color increases with usage.
Missing dates have outlined tiles; returned zeros are shown separately. The radar
shows each of the latest seven calendar dates, omitting missing observations rather
than drawing them as zero. The donut partitions returned tokens into the latest
seven days and earlier dates.

Run `python3 .github/profile/update_codex_city.py` to read the existing local Codex
login and render both sizes. Add `--publish` to update only `codex-city.json`,
`codex-city.svg`, and `codex-city-mobile.svg`. The updater makes no model inference
calls and does not read or reset quota limits.

Values come from the official app-server `account/usage/read` response's
`dailyUsageBuckets`, preserving `startDate` without timezone conversion. These
buckets have no input/output/cache breakdown, and complete all-device coverage is
not established. Only dates, token counts, coverage and collection time are exported.
No conversations, thread metadata, projects, paths, credentials, account identifiers
or quota data are published. Invalid, duplicate, stale or unavailable data stops
publication. The publisher updates an explicit three-file allowlist against the
latest remote tree, rejects concurrent non-fast-forward changes and reads all three
files back after publishing.

The signed-in Mac refreshes this card daily at 09:30 Asia/Shanghai and must be online.
The updater never changes the README, the snake or the blog.

## GitHub contribution snake

`.github/workflows/profile-snake.yml` uses pinned `Platane/snk` v3.5.0 to generate
dark and light mint animations daily at 09:23 Asia/Shanghai on GitHub Actions. It
can also be started manually. It stages only `github-snake-dark.svg` and
`github-snake.svg`; commits contain `[skip deploy]`.

The snake uses GitHub's contribution calendar, including qualifying commits and
other contribution types. It is not a count of every local git commit. The README
uses the dark mint palette to match NightView; a light variant is also generated.
