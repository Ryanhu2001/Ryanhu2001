# Turn This Into A Personal Academic Site

## Current Remote

Use this remote:

```text
git@github.com:Ryanhu2001/Ryanhu2001.git
```

After pushing, enable Pages in GitHub:

1. Open the repository on GitHub.
2. Go to `Settings -> Pages`.
3. Set `Source` to `GitHub Actions`.
4. Save.

The included workflow builds the site and deploys `docs/`.

## Resulting URL

Because the repo is `Ryanhu2001/Ryanhu2001`, the project-page URL is:

```text
https://ryanhu2001.github.io/Ryanhu2001/
```

If you want the root personal domain:

```text
https://ryanhu2001.github.io/
```

use a repository named:

```text
Ryanhu2001.github.io
```

## Publishing A Note

Add this to the top of a note:

```yaml
---
title: My Note
public: true
---
```

Then rebuild:

```sh
node scripts/build-wiki.mjs
```

## Editing The Homepage

Edit:

```sh
site/profile.json
```

Then rebuild:

```sh
node scripts/build-wiki.mjs
```
