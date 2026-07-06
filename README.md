# Ryan

Personal site and public wiki.

Based on [academic-homepage](https://github.com/luost26/academic-homepage). Public notes live in `wiki/` and use:

```yaml
public: true
```

Assets live in `assets/`.

## Edit

- Homepage content: `index.md`
- Profile data: `_data/profile.yml`
- Navigation: `_data/navigation.yml`
- Wiki index: `wiki/index.md`
- Wiki notes: add Markdown files under `wiki/`

Write homepage Markdown below the front matter in `index.md`; the layout is handled by `_layouts/home.html`.

## Publish

Push to `main`. GitHub Actions builds the Jekyll site and deploys `_site/` to the `gh-pages` branch.
