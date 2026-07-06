# Personal Wiki

This repository is both an Obsidian vault and a publishable personal wiki.

## Local Writing

Open this folder as an Obsidian vault:

```sh
/Users/ryan/personal-wiki
```

Recommended flow:

1. Capture raw material in `00_Inbox/`.
2. Promote useful notes into `10_Notes/`.
3. Keep active work in `20_Projects/`.
4. Draft public writing in `30_Blog/`.
5. Maintain topic indexes in `40_Maps/`.

## Public Wiki

Only notes with frontmatter `public: true` are published.

Build the static site:

```sh
node scripts/build-wiki.mjs
```

The generated site is written to `docs/`, so GitHub Pages can publish from:

```text
Branch: main
Folder: /docs
```

## First GitHub Pages Link

After pushing this repo to GitHub and enabling Pages, your public wiki link will be:

```text
https://<github-username>.github.io/<repo-name>/
```

For example:

```text
https://ryan.github.io/personal-wiki/
```

## Plugins

The vault is configured for a small plugin set:

- Obsidian Git
- Dataview
- Templater
- Style Settings
- Omnisearch
- Linter
- QuickAdd

If the plugin files are not present under `.obsidian/plugins/`, open Obsidian, enable Community Plugins, and install them by name.

