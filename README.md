# Ryan Hu Academic Homepage + Wiki

This repository is both an Obsidian vault and a publishable academic homepage.

- `docs/index.html` is the public academic homepage.
- `docs/wiki/` is the public wiki generated from Obsidian notes.
- `site/profile.json` controls the homepage profile, links, interests, news, projects, and publications.

## Local Writing

Open this folder as an Obsidian vault:

```sh
/Users/ryan/personal-wiki
```

Use a deliberately small structure:

- `wiki/` for notes that may become public wiki pages.
- `assets/` for images and attachments used by notes.
- `site/profile.json` for the academic homepage profile.
- `docs/` for the generated public site.

## Public Wiki

Only notes with frontmatter `public: true` are published.

Create or edit notes under `wiki/`, for example:

```yaml
---
title: My Note
public: true
description: One sentence summary.
---
```

Build the static site:

```sh
node scripts/build-wiki.mjs
```

The generated site is written to `docs/`.

## Automated Publishing

The repo includes a GitHub Actions workflow:

```text
.github/workflows/build-site.yml
```

When a pushed commit changes Markdown notes, `assets/`, `site/`, or `scripts/build-wiki.mjs`, GitHub automatically rebuilds `docs/` and commits the generated site back to `main`.

With the Obsidian Git plugin, the daily workflow becomes:

```text
write in Obsidian -> Obsidian Git pushes -> GitHub Actions rebuilds docs -> GitHub Pages updates
```

## GitHub Pages

This repo is ready for GitHub Pages branch publishing. With the provided remote:

```text
git@github.com:Ryanhu2001/Ryanhu2001.git
```

set GitHub Pages to:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

The project-page URL will be:

```text
https://ryanhu2001.github.io/Ryanhu2001/
```

For the clean root URL:

```text
https://ryanhu2001.github.io/
```

create or rename the repository to `Ryanhu2001.github.io`.

For `ryan.wiki`, update DNS away from Namecheap forwarding and toward GitHub Pages. The exact DNS records are in `GITHUB_PAGES.md`.

## Editing The Homepage

Edit:

```sh
site/profile.json
```

Then rebuild with `node scripts/build-wiki.mjs`.

## Plugins

The vault is configured for a small plugin set:

- Obsidian Git
- Dataview
- Style Settings
- Omnisearch
- Linter

If the plugin files are not present under `.obsidian/plugins/`, open Obsidian, enable Community Plugins, and install them by name.
