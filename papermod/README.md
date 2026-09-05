# PaperMod + Nord

The public homepage and three English notes use the complete upstream PaperMod theme, pinned to commit `d3768854d00ad003b0a8dbdba254ce9224377a01`. The unmodified theme and its MIT license are vendored under `themes/PaperMod`. Nord changes colors only; layout and typography remain upstream. Local hooks provide the SVG favicon, base-path-safe assets, and build-time math.

`npm run build` builds the legacy Jekyll site, renders these pages with Hugo **0.165.0**, composes the outputs, and indexes the result with Pagefind. Set `HUGO_BINARY` to an explicit executable if `hugo` is not on PATH. CI installs the pinned Hugo release with a SHA-256 check. Push source to `main`; the existing deployment action owns `gh-pages`.

Hugo owns the homepage and these routes:

- `/wiki/Linear%20Attention.html`
- `/wiki/kv-cache/`
- `/wiki/rotary-position-embeddings/`

All other Jekyll wiki and paper-reading routes remain intact, including `/wiki/`. Section generation is disabled so Hugo cannot overwrite that index. The Wiki navigation links there. Other notes are not migrated.

Linear Attention is the reviewed English adaptation of the original topic note. KV Cache and Rotary Position Embeddings are explanatory sample posts, not reports of personal experiments. The hybrid-attention illustration is a compact native draw.io SVG; editable source is stored under `diagrams/linear-attention/`, outside published output. It omits vision, sublayer normalization, internal residual wiring, and Qwen's n-gram/MTP branches; the article states that scope and links the official architecture reports.

KaTeX **0.16.21** matches Hugo's renderer and is hosted locally with its MIT license. Math renders to HTML and accessible MathML during the build. No remote rendering script or font service is required.

Generated site output, local validation screenshots, temporary preview servers, retired figures, and historical migration receipts are not committed.
