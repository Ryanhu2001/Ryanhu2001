import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outDir = path.join(root, "docs");
const pageDir = path.join(outDir, "pages");
const ignoredDirs = new Set([".git", ".obsidian", "docs", "scripts", "assets"]);

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".") && entry.name !== ".github") continue;
    const full = path.join(dir, entry.name);
    const rel = path.relative(root, full);
    const first = rel.split(path.sep)[0];
    if (ignoredDirs.has(first)) continue;
    if (entry.isDirectory()) {
      files.push(...walk(full));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      files.push(full);
    }
  }
  return files;
}

function parseFrontmatter(raw) {
  if (!raw.startsWith("---\n")) return { data: {}, body: raw };
  const end = raw.indexOf("\n---", 4);
  if (end === -1) return { data: {}, body: raw };
  const fm = raw.slice(4, end).trim();
  const body = raw.slice(end + 4).replace(/^\n/, "");
  const data = {};
  for (const line of fm.split(/\n/)) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) continue;
    const key = match[1];
    let value = match[2].trim();
    if (value === "true") value = true;
    else if (value === "false") value = false;
    else value = value.replace(/^["']|["']$/g, "");
    data[key] = value;
  }
  return { data, body };
}

function slugify(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/['"]/g, "")
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "") || "note";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineMarkdown(text, noteByKey, linkPrefix = "") {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  html = html.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (_, target, label) => wikiLink(target, label, noteByKey, linkPrefix));
  html = html.replace(/\[\[([^\]]+)\]\]/g, (_, target) => wikiLink(target, target.split("/").pop(), noteByKey, linkPrefix));
  return html;
}

function wikiLink(target, label, noteByKey, linkPrefix = "") {
  const clean = String(target).replace(/\.md$/, "");
  const key = slugify(clean.split("/").pop());
  const note = noteByKey.get(key) || noteByKey.get(slugify(clean));
  if (!note) return `<span class="missing-link">${escapeHtml(label)}</span>`;
  return `<a href="${linkPrefix}${note.href}">${escapeHtml(label)}</a>`;
}

function markdownToHtml(markdown, noteByKey, linkPrefix = "") {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let inCode = false;
  let code = [];
  let inList = false;

  function closeList() {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        code = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    if (!line.trim()) {
      closeList();
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      const text = inlineMarkdown(heading[2], noteByKey, linkPrefix);
      const id = slugify(heading[2]);
      html.push(`<h${level} id="${id}">${text}</h${level}>`);
      continue;
    }
    const list = line.match(/^\s*[-*]\s+(.*)$/);
    if (list) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(list[1], noteByKey, linkPrefix)}</li>`);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(quote[1], noteByKey, linkPrefix)}</blockquote>`);
      continue;
    }
    closeList();
    html.push(`<p>${inlineMarkdown(line, noteByKey, linkPrefix)}</p>`);
  }
  closeList();
  return html.join("\n");
}

function layout({ title, description = "", body, nav }) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(description)}">
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <aside class="sidebar">
    <a class="brand" href="../index.html">Personal Wiki</a>
    <nav>${nav}</nav>
  </aside>
  <main class="page">
    ${body}
  </main>
</body>
</html>`;
}

function indexLayout({ title, body, nav }) {
  return layout({ title, body, nav }).replace('href="../style.css"', 'href="style.css"').replaceAll("../index.html", "index.html").replaceAll('href="pages/', 'href="pages/');
}

function ensureCleanDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

const files = walk(root);
const notes = files.map((file) => {
  const raw = fs.readFileSync(file, "utf8");
  const { data, body } = parseFrontmatter(raw);
  const rel = path.relative(root, file);
  const inferredTitle = path.basename(file, ".md");
  const title = data.title || inferredTitle;
  const slug = slugify(rel.replace(/\.md$/, ""));
  const href = `pages/${slug}.html`;
  return { file, rel, data, body, title, slug, href };
}).filter((note) => note.data.public === true);

const noteByKey = new Map();
for (const note of notes) {
  noteByKey.set(slugify(note.title), note);
  noteByKey.set(slugify(path.basename(note.file, ".md")), note);
  noteByKey.set(slugify(note.rel.replace(/\.md$/, "")), note);
}

ensureCleanDir(outDir);
fs.mkdirSync(pageDir, { recursive: true });

const nav = notes
  .sort((a, b) => a.title.localeCompare(b.title))
  .map((note) => `<a href="../${note.href}">${escapeHtml(note.title)}</a>`)
  .join("\n");

for (const note of notes) {
  const body = markdownToHtml(note.body, noteByKey, "../");
  const page = layout({
    title: note.title,
    description: note.data.description || "",
    body,
    nav
  });
  fs.writeFileSync(path.join(pageDir, `${note.slug}.html`), page);
}

const home = notes.find((note) => note.title.toLowerCase() === "home") || notes[0];
const indexBody = home ? markdownToHtml(home.body, noteByKey) : "<h1>Personal Wiki</h1>";
const indexNav = nav.replaceAll('href="../', 'href="');
fs.writeFileSync(path.join(outDir, "index.html"), indexLayout({
  title: "Personal Wiki",
  body: indexBody,
  nav: indexNav
}));

fs.writeFileSync(path.join(outDir, "style.css"), `:root {
  color-scheme: light;
  --bg: #fbfbf8;
  --panel: #f1f0ea;
  --text: #22231f;
  --muted: #6b6c63;
  --line: #dedbd0;
  --accent: #3f7f6b;
  --accent-2: #2d6f8f;
  --code: #ecebe4;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  line-height: 1.65;
  letter-spacing: 0;
}
a { color: var(--accent-2); text-decoration-thickness: 1px; text-underline-offset: 3px; }
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 260px;
  padding: 28px 20px;
  border-right: 1px solid var(--line);
  background: var(--panel);
  overflow: auto;
}
.brand {
  display: block;
  margin-bottom: 24px;
  color: var(--text);
  font-size: 18px;
  font-weight: 760;
  text-decoration: none;
}
nav a {
  display: block;
  padding: 7px 0;
  color: var(--muted);
  text-decoration: none;
}
nav a:hover { color: var(--text); }
.page {
  max-width: 860px;
  margin-left: 260px;
  padding: 56px 52px 96px;
}
h1, h2, h3, h4 {
  line-height: 1.25;
  letter-spacing: 0;
}
h1 { font-size: 40px; margin: 0 0 28px; }
h2 { font-size: 25px; margin-top: 42px; }
h3 { font-size: 19px; margin-top: 30px; }
p, li { font-size: 17px; }
code {
  background: var(--code);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.92em;
}
pre {
  background: var(--code);
  padding: 16px;
  border-radius: 8px;
  overflow: auto;
}
pre code { padding: 0; }
blockquote {
  margin: 20px 0;
  padding-left: 16px;
  border-left: 3px solid var(--accent);
  color: var(--muted);
}
.missing-link {
  color: #9a4f45;
  border-bottom: 1px dotted #9a4f45;
}
@media (max-width: 760px) {
  .sidebar {
    position: static;
    width: auto;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .page {
    margin-left: 0;
    padding: 34px 22px 72px;
  }
  h1 { font-size: 32px; }
}
`);

console.log(`Built ${notes.length} public notes into docs/`);
