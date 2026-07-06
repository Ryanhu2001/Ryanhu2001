# Turn This Into A Personal Wiki Link

## Option A: GitHub Pages From `/docs`

1. Create a GitHub repository, for example `personal-wiki`.
2. Push this local repo to GitHub.
3. Open the repository on GitHub.
4. Go to `Settings -> Pages`.
5. Set:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

6. Save.

Your wiki will be available at:

```text
https://<github-username>.github.io/<repo-name>/
```

## Push Commands

After creating the GitHub repo:

```sh
cd /Users/ryan/personal-wiki
git remote add origin git@github.com:<github-username>/<repo-name>.git
git push -u origin main
```

If you prefer HTTPS:

```sh
git remote add origin https://github.com/<github-username>/<repo-name>.git
git push -u origin main
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

