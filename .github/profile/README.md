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
totals cover all exported completed Codex dates. Each bar represents a daily token value,
with the upstream logarithmic mapping applied in millions of tokens. A shared fit
factor keeps larger future peaks within the canvas. Color increases with usage.
Missing dates have outlined tiles; returned zeros are shown separately. The radar
shows each of the latest seven calendar dates, omitting missing observations rather
than drawing them as zero. The donut partitions returned tokens into the latest
seven days and earlier dates.

Run `python3 .github/profile/update_codex_city.py` on the Mac with Token Monitor
automatic export enabled. The updater reads its configured export directory from
the local Token Monitor settings and opens `token-monitor-export.json`. An explicit
`--monitor-export /path/to/token-monitor-export.json` is also supported. Add
`--publish` to update only `codex-city.json`, `codex-city.svg`, and
`codex-city-mobile.svg`. No Codex login, model inference, quota request, or quota
reset is used. The full Token Monitor export stays local.

Values come directly from Token Monitor's `daily[].perClient.codex.tokens`.
Other clients are excluded. The exported total already includes cache and reasoning;
their component fields are never added again. Token Monitor supplies the history
from its configured source, including Hub history when configured. This mirrors
Token Monitor's records, without establishing complete all-device coverage or
independently verifying its session deduplication.

Date keys are preserved without shifting them. Today's date in Asia/Shanghai is
excluded because its count is still changing. The chart's total is the sum of those
completed daily records, so it can differ from Token Monitor's live All Time snapshot.
An absent Codex entry is missing data; only an explicit zero is plotted as zero.
Schema version 2 identifies the source change and includes the export timestamp.
Only dates, token counts, coverage and collection/export times are published.
No conversations, thread metadata, projects, paths, credentials, account identifiers
or quota data are published. Invalid or duplicate dates, inconsistent components,
exports older than 48 hours, history over three days behind, or unavailable exports
stop publication and preserve the online images. The old account API is never used
as a substitute. The publisher updates an explicit three-file allowlist against the
latest remote tree, rejects concurrent non-fast-forward changes and reads all three
files back after publishing.

The Mac refreshes this card daily at 09:30 Asia/Shanghai and must be online, with a
recent automatic export from Token Monitor.
The updater never changes the README, the snake or the blog.

Validate the data contract with `python3 -m unittest discover -s .github/profile -p 'test_codex_city.py'`.

## GitHub contribution snake

`.github/workflows/profile-snake.yml` uses pinned `Platane/snk` v3.5.0 to generate
dark and light mint animations daily at 09:23 Asia/Shanghai on GitHub Actions. It
can also be started manually. It stages only `github-snake-dark.svg` and
`github-snake.svg`; commits contain `[skip deploy]`.

The snake uses GitHub's contribution calendar, including qualifying commits and
other contribution types. It is not a count of every local git commit. The README
uses the dark mint palette to match NightView; a light variant is also generated.
