# Ryan

Personal site and public wiki.

Based on [academic-homepage](https://github.com/luost26/academic-homepage). Public notes live in `wiki/` and use:

```yaml
public: true
```

Assets live in `assets/`.

## Edit

- Homepage layout: `index.html`
- Profile data: `_data/profile.yml`
- Navigation: `_data/navigation.yml`
- Wiki index: `wiki/index.md`
- Wiki notes: add Markdown files under `wiki/`

## Publish

Push to `main`. GitHub Actions builds the Jekyll site and deploys `_site/` to the `gh-pages` branch.
