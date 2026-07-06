# Turn This Into A Personal Academic Site

## Current Remote

Use this remote:

```text
git@github.com:Ryanhu2001/Ryanhu2001.git
```

After pushing, enable Pages in GitHub:

1. Open the repository on GitHub.
2. Go to `Settings -> Pages`.
3. Set `Source` to `Deploy from a branch`.
4. Set `Branch` to `main` and folder to `/docs`.
4. Save.

The generated static site is already committed under `docs/`.

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

## Custom Domain: `ryan.wiki`

Current DNS check shows:

```text
ryan.wiki        A      162.255.119.128
www.ryan.wiki    CNAME  parkingpage.namecheap.com
```

That is Namecheap forwarding/parking, not GitHub Pages.

To use `ryan.wiki`, remove Namecheap URL forwarding and set DNS to GitHub Pages:

```text
@    A      185.199.108.153
@    A      185.199.109.153
@    A      185.199.110.153
@    A      185.199.111.153
www  CNAME  Ryanhu2001.github.io
```

Then in GitHub `Settings -> Pages`, set `Custom domain` to:

```text
ryan.wiki
```

Until DNS is fixed, remove the custom domain in GitHub Pages settings if you want the default `github.io` URL to work.

## Publishing A Note

Put the note under `wiki/` and add this to the top:

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

If the note is committed and pushed without running the build locally, GitHub Actions will rebuild `docs/` automatically and commit the generated site back to `main`.

## Editing The Homepage

Edit:

```sh
site/profile.json
```

Then rebuild:

```sh
node scripts/build-wiki.mjs
```
