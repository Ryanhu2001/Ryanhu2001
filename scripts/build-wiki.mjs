import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const outDir = path.join(root, "docs");
const wikiDir = path.join(outDir, "wiki");
const profilePath = path.join(root, "site", "profile.json");
const ignoredDirs = new Set([".git", ".obsidian", "docs", "scripts", "assets", "site"]);

const defaultProfile = {
  name: "Ryan Hu",
  initials: "RH",
  role: "Researcher / Engineer",
  affiliation: "",
  location: "",
  email: "",
  headline: "I work on LLM agents, reinforcement learning, evaluation, and practical systems for thinking with models.",
  bio: [
    "This site is a personal academic homepage and a public knowledge base. The homepage collects profile, research interests, projects, writing, and selected work. The wiki publishes curated Obsidian notes."
  ],
  interests: [
    "LLM agents",
    "computer-use agents",
    "reinforcement learning",
    "evaluation",
    "personal knowledge systems"
  ],
  links: [
    { "label": "GitHub", "url": "https://github.com/Ryanhu2001" }
  ],
  news: [
    { "date": "2026-07", "text": "Launched this academic homepage and public wiki." }
  ],
  publications: [],
  projects: [
    {
      "title": "Personal Wiki",
      "description": "An Obsidian-first knowledge base published as a lightweight static site.",
      "url": "wiki/index.html"
    }
  ]
};

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

function readProfile() {
  if (!fs.existsSync(profilePath)) return defaultProfile;
  const userProfile = JSON.parse(fs.readFileSync(profilePath, "utf8"));
  return {
    ...defaultProfile,
    ...userProfile,
    links: userProfile.links || defaultProfile.links,
    bio: userProfile.bio || defaultProfile.bio,
    interests: userProfile.interests || defaultProfile.interests,
    news: userProfile.news || defaultProfile.news,
    publications: userProfile.publications || defaultProfile.publications,
    projects: userProfile.projects || defaultProfile.projects
  };
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
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function unescapeMarkdownText(value) {
  return String(value ?? "").replace(/\\([\\`*_\[\](){}#+\-.!<>|+])/g, "$1");
}

function stripMarkdown(value) {
  return unescapeMarkdownText(value)
    .replace(/```[\s\S]*?```/g, "")
    .replace(/^#+\s+/gm, "")
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "$1")
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2")
    .replace(/\[\[([^\]]+)\]\]/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/[`*_>#]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function getExcerpt(note) {
  const lines = note.body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.startsWith("#") && !line.startsWith("```"));
  const excerpt = stripMarkdown(lines[0] || note.data.description || "");
  return excerpt.length > 150 ? `${excerpt.slice(0, 147)}...` : excerpt;
}

function isExternalUrl(value) {
  return /^(https?:|mailto:|#|\/)/i.test(String(value));
}

function assetUrl(value, linkPrefix = "") {
  const clean = unescapeMarkdownText(String(value || "").trim());
  if (!clean || isExternalUrl(clean)) return clean;
  return `${linkPrefix}${clean}`;
}

function inlineMarkdown(text, noteByKey, linkPrefix = "") {
  let html = escapeHtml(unescapeMarkdownText(text));
  html = html.replace(/&lt;br\s*\/?&gt;/gi, "<br>");
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
    const caption = alt ? `<figcaption>${alt}</figcaption>` : "";
    return `<figure><img src="${assetUrl(src, linkPrefix)}" alt="${alt}" loading="lazy">${caption}</figure>`;
  });
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

function isTableSeparator(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function isTableRow(line) {
  return line.includes("|") && !line.startsWith("```");
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderTable(rows, noteByKey, linkPrefix = "") {
  if (rows.length < 2) return "";
  const headers = splitTableRow(rows[0]);
  const bodyRows = rows.slice(2).map(splitTableRow);
  const head = headers.map((cell) => `<th>${inlineMarkdown(cell, noteByKey, linkPrefix)}</th>`).join("");
  const body = bodyRows
    .map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell, noteByKey, linkPrefix)}</td>`).join("")}</tr>`)
    .join("\n");
  return `<div class="table-wrap"><table>
<thead><tr>${head}</tr></thead>
<tbody>
${body}
</tbody>
</table></div>`;
}

function markdownToHtml(markdown, noteByKey, linkPrefix = "") {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let inCode = false;
  let code = [];
  let listType = null;

  function closeList() {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  }

  function openList(type) {
    if (listType !== type) {
      closeList();
      html.push(`<${type}>`);
      listType = type;
    }
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
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
    if (isTableRow(line) && isTableSeparator(lines[i + 1] || "")) {
      closeList();
      const tableRows = [line, lines[i + 1]];
      i += 2;
      while (i < lines.length && isTableRow(lines[i]) && lines[i].trim()) {
        tableRows.push(lines[i]);
        i += 1;
      }
      i -= 1;
      html.push(renderTable(tableRows, noteByKey, linkPrefix));
      continue;
    }
    if (!line.trim()) {
      closeList();
      continue;
    }
    if (/^\s*-{3,}\s*$/.test(line)) {
      closeList();
      html.push("<hr>");
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
    const unorderedList = line.match(/^\s*[-*]\s+(.*)$/);
    if (unorderedList) {
      openList("ul");
      html.push(`<li>${inlineMarkdown(unorderedList[1], noteByKey, linkPrefix)}</li>`);
      continue;
    }
    const orderedList = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (orderedList) {
      openList("ol");
      html.push(`<li>${inlineMarkdown(orderedList[1], noteByKey, linkPrefix)}</li>`);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(quote[1], noteByKey, linkPrefix)}</blockquote>`);
      continue;
    }
    closeList();
    const rendered = inlineMarkdown(line, noteByKey, linkPrefix);
    html.push(rendered.startsWith("<figure>") ? rendered : `<p>${rendered}</p>`);
  }
  closeList();
  return html.join("\n");
}

function shell({ title, description = "", body, active = "home", base = "", brand = "Ryan Hu" }) {
  const homeActive = active === "home" ? "active" : "";
  const wikiActive = active === "wiki" ? "active" : "";
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(description)}">
  <link rel="stylesheet" href="${base}style.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="${base}index.html">${escapeHtml(brand)}</a>
    <nav class="site-nav" aria-label="Main navigation">
      <a class="${homeActive}" href="${base}index.html">Home</a>
      <a class="${wikiActive}" href="${base}wiki/index.html">Wiki</a>
    </nav>
  </header>
  <main>
    ${body}
  </main>
</body>
</html>`;
}

function linkList(links, className = "button") {
  return (links || [])
    .filter((link) => link && link.url && link.label)
    .map((link) => `<a class="${className}" href="${escapeHtml(link.url)}">${escapeHtml(link.label)}</a>`)
    .join("\n");
}

function renderAcademicHome(profile, notes) {
  const profileLinks = linkList(profile.links, "button secondary");
  const contactLinks = [
    profile.email ? `<a class="button secondary" href="mailto:${escapeHtml(profile.email)}">Email</a>` : "",
    profileLinks
  ].filter(Boolean).join("\n");
  const bio = (profile.bio || []).map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("\n");
  const interests = (profile.interests || []).map((interest) => `<span>${escapeHtml(interest)}</span>`).join("\n");
  const news = (profile.news || []).map((item) => `
    <li>
      <time>${escapeHtml(item.date)}</time>
      <span>${escapeHtml(item.text)}</span>
    </li>`).join("\n");
  const publications = (profile.publications || []).map((item) => `
    <article class="entry">
      <h3>${escapeHtml(item.title)}</h3>
      <p class="entry-meta">${escapeHtml([item.authors, item.venue, item.year].filter(Boolean).join(" · "))}</p>
      ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}
      <div class="entry-links">${linkList(item.links || [], "text-link")}</div>
    </article>`).join("\n");
  const projects = (profile.projects || []).map((item) => `
    <article class="entry">
      <h3>${escapeHtml(item.title)}</h3>
      ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}
      ${item.url ? `<a class="text-link" href="${escapeHtml(item.url)}">Open</a>` : ""}
    </article>`).join("\n");
  const featuredNotes = notes
    .filter((note) => note.title.toLowerCase() !== "home")
    .slice(0, 4)
    .map((note) => `
      <article class="entry compact">
        <h3><a href="${note.href}">${escapeHtml(note.title)}</a></h3>
        ${getExcerpt(note) ? `<p>${escapeHtml(getExcerpt(note))}</p>` : ""}
      </article>`)
    .join("\n");

  const affiliation = [profile.role, profile.affiliation, profile.location].filter(Boolean).join(" · ");
  const initials = profile.initials || profile.name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2);

  return `
  <section class="hero">
    <div class="hero-copy">
      <p class="eyebrow">Academic homepage and public notebook</p>
      <h1>${escapeHtml(profile.name)}</h1>
      <p class="lede">${escapeHtml(profile.headline)}</p>
      ${affiliation ? `<p class="affiliation">${escapeHtml(affiliation)}</p>` : ""}
      <div class="actions">
        <a class="button primary" href="wiki/index.html">Open Wiki</a>
        ${contactLinks}
      </div>
    </div>
    <aside class="identity-panel" aria-label="Profile summary">
      <div class="avatar">${escapeHtml(initials)}</div>
      <div>
        <strong>${escapeHtml(profile.name)}</strong>
        <span>${escapeHtml(profile.role)}</span>
      </div>
    </aside>
  </section>

  <section class="content-grid">
    <div class="main-column">
      <section class="section">
        <h2>About</h2>
        ${bio}
      </section>

      ${projects ? `<section class="section">
        <h2>Projects</h2>
        <div class="entry-list">${projects}</div>
      </section>` : ""}

      ${publications ? `<section class="section">
        <h2>Publications</h2>
        <div class="entry-list">${publications}</div>
      </section>` : ""}

      ${featuredNotes ? `<section class="section">
        <h2>From The Wiki</h2>
        <div class="entry-list">${featuredNotes}</div>
      </section>` : ""}
    </div>

    <aside class="side-column">
      ${interests ? `<section class="section">
        <h2>Interests</h2>
        <div class="tag-list">${interests}</div>
      </section>` : ""}
      ${news ? `<section class="section">
        <h2>News</h2>
        <ul class="news-list">${news}</ul>
      </section>` : ""}
    </aside>
  </section>`;
}

function renderWikiIndex(notes) {
  const notesHtml = notes
    .sort((a, b) => a.title.localeCompare(b.title))
    .map((note) => `
      <article class="entry">
        <h2><a href="../${note.href}">${escapeHtml(note.title)}</a></h2>
        ${getExcerpt(note) ? `<p>${escapeHtml(getExcerpt(note))}</p>` : ""}
        <p class="entry-meta">${escapeHtml(note.rel)}</p>
      </article>`)
    .join("\n");

  return `
  <section class="page-shell">
    <div class="page-heading">
      <p class="eyebrow">Public notes</p>
      <h1>Wiki</h1>
      <p class="lede">Curated notes from the Obsidian vault. Only notes with <code>public: true</code> are published here.</p>
    </div>
    <div class="entry-list">${notesHtml}</div>
  </section>`;
}

function ensureCleanDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

function writeText(file, content) {
  fs.writeFileSync(file, `${String(content).replace(/[ \t]+$/gm, "").trimEnd()}\n`);
}

function copyDir(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else if (entry.isFile()) {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

const profile = readProfile();
const files = walk(root);
const notes = files.map((file) => {
  const raw = fs.readFileSync(file, "utf8");
  const { data, body } = parseFrontmatter(raw);
  const rel = path.relative(root, file);
  const inferredTitle = path.basename(file, ".md");
  const title = data.title || inferredTitle;
  const slug = slugify(rel.replace(/\.md$/, ""));
  const href = `wiki/${slug}.html`;
  return { file, rel, data, body, title, slug, href };
}).filter((note) => note.data.public === true);

const noteByKey = new Map();
for (const note of notes) {
  noteByKey.set(slugify(note.title), note);
  noteByKey.set(slugify(path.basename(note.file, ".md")), note);
  noteByKey.set(slugify(note.rel.replace(/\.md$/, "")), note);
}

ensureCleanDir(outDir);
fs.mkdirSync(wikiDir, { recursive: true });
copyDir(path.join(root, "assets"), path.join(outDir, "assets"));
fs.writeFileSync(path.join(outDir, ".nojekyll"), "");

for (const note of notes) {
  const body = `
  <article class="note page-shell">
    <a class="back-link" href="index.html">Wiki index</a>
    ${markdownToHtml(note.body, noteByKey, "../")}
  </article>`;
  const page = shell({
    title: `${note.title} | Wiki`,
    description: note.data.description || getExcerpt(note),
    body,
    active: "wiki",
    base: "../",
    brand: profile.name
  });
  writeText(path.join(wikiDir, `${note.slug}.html`), page);
}

writeText(path.join(wikiDir, "index.html"), shell({
  title: `Wiki | ${profile.name}`,
  description: `Public notes from ${profile.name}'s Obsidian vault.`,
  body: renderWikiIndex(notes),
  active: "wiki",
  base: "../",
  brand: profile.name
}));

writeText(path.join(outDir, "index.html"), shell({
  title: `${profile.name} | Academic Homepage`,
  description: profile.headline,
  body: renderAcademicHome(profile, notes),
  active: "home",
  base: "",
  brand: profile.name
}));

writeText(path.join(outDir, "style.css"), `:root {
  color-scheme: light;
  --bg: #f8f8f4;
  --paper: #ffffff;
  --ink: #20231f;
  --muted: #68706a;
  --line: #dcded6;
  --soft: #ecefe8;
  --accent: #1f6f78;
  --accent-strong: #174f58;
  --warm: #9f5d34;
  --code: #eff1eb;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  line-height: 1.65;
  letter-spacing: 0;
}

a {
  color: var(--accent-strong);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 68px;
  padding: 0 36px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 92%, white);
  backdrop-filter: blur(16px);
}

.brand {
  color: var(--ink);
  font-weight: 780;
  text-decoration: none;
}

.site-nav {
  display: flex;
  gap: 8px;
}

.site-nav a {
  min-width: 72px;
  padding: 7px 12px;
  border: 1px solid transparent;
  color: var(--muted);
  text-align: center;
  text-decoration: none;
}

.site-nav a:hover,
.site-nav a.active {
  border-color: var(--line);
  color: var(--ink);
  background: var(--paper);
}

main {
  width: min(1120px, calc(100% - 44px));
  margin: 0 auto;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 44px;
  align-items: end;
  min-height: calc(100vh - 68px);
  padding: 76px 0 54px;
  border-bottom: 1px solid var(--line);
}

.hero-copy {
  max-width: 760px;
}

.eyebrow {
  margin: 0 0 14px;
  color: var(--warm);
  font-size: 13px;
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
h4 {
  line-height: 1.2;
  letter-spacing: 0;
}

h1 {
  margin: 0 0 18px;
  font-size: clamp(40px, 7vw, 82px);
  font-weight: 820;
}

h2 {
  margin: 0 0 18px;
  font-size: 24px;
}

h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

p,
li {
  font-size: 16px;
}

.lede {
  max-width: 760px;
  margin: 0 0 18px;
  color: var(--muted);
  font-size: 21px;
  line-height: 1.55;
}

.affiliation {
  margin: 0 0 28px;
  color: var(--muted);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 8px 14px;
  border: 1px solid var(--line);
  color: var(--ink);
  background: var(--paper);
  text-decoration: none;
}

.button.primary {
  border-color: var(--accent);
  color: white;
  background: var(--accent);
}

.button.secondary:hover,
.button.primary:hover {
  transform: translateY(-1px);
}

.identity-panel {
  display: grid;
  gap: 18px;
  padding: 22px;
  border: 1px solid var(--line);
  background: var(--paper);
}

.avatar {
  display: grid;
  width: 128px;
  height: 128px;
  place-items: center;
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(31, 111, 120, 0.14), rgba(159, 93, 52, 0.12)),
    var(--soft);
  color: var(--accent-strong);
  font-size: 42px;
  font-weight: 820;
}

.identity-panel strong,
.identity-panel span {
  display: block;
}

.identity-panel span {
  color: var(--muted);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 56px;
  padding: 52px 0 92px;
}

.main-column,
.side-column {
  display: grid;
  align-content: start;
  gap: 44px;
}

.section {
  min-width: 0;
}

.entry-list {
  display: grid;
  gap: 18px;
}

.entry {
  padding: 0 0 18px;
  border-bottom: 1px solid var(--line);
}

.entry.compact h3 {
  margin-bottom: 4px;
}

.entry p {
  margin: 8px 0 0;
}

.entry-meta {
  color: var(--muted);
  font-size: 14px;
}

.entry-links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.text-link {
  font-weight: 680;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-list span {
  padding: 5px 9px;
  border: 1px solid var(--line);
  background: var(--paper);
  color: var(--muted);
  font-size: 14px;
}

.news-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.news-list li {
  display: grid;
  gap: 2px;
  font-size: 15px;
}

.news-list time {
  color: var(--warm);
  font-size: 13px;
  font-weight: 720;
}

.page-shell {
  max-width: 820px;
  padding: 60px 0 96px;
}

.page-heading {
  margin-bottom: 38px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--line);
}

.note h1 {
  font-size: 44px;
}

.note h2 {
  margin-top: 42px;
}

.note h3 {
  margin-top: 30px;
}

.back-link {
  display: inline-block;
  margin-bottom: 28px;
  color: var(--muted);
  text-decoration: none;
}

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
  border-radius: 6px;
  overflow: auto;
}

pre code {
  padding: 0;
}

hr {
  margin: 34px 0;
  border: 0;
  border-top: 1px solid var(--line);
}

figure {
  margin: 28px 0;
}

figure img,
.note img {
  display: block;
  max-width: 100%;
  height: auto;
  border: 1px solid var(--line);
  background: var(--paper);
}

figcaption {
  margin-top: 8px;
  color: var(--muted);
  font-size: 13px;
  text-align: center;
}

.table-wrap {
  margin: 24px 0;
  overflow-x: auto;
  border: 1px solid var(--line);
  background: var(--paper);
}

table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  border-right: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}

th {
  background: var(--soft);
  font-size: 14px;
}

td {
  font-size: 14px;
}

tr:last-child td {
  border-bottom: 0;
}

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

@media (max-width: 840px) {
  .site-header {
    padding: 0 20px;
  }

  main {
    width: min(100% - 32px, 1120px);
  }

  .hero,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .hero {
    min-height: auto;
    padding: 54px 0 42px;
  }

  .identity-panel {
    max-width: 360px;
  }

  .content-grid {
    gap: 36px;
    padding-top: 40px;
  }

  .lede {
    font-size: 18px;
  }

  .note h1 {
    font-size: 34px;
  }
}

@media (max-width: 520px) {
  .site-header {
    min-height: 62px;
  }

  .site-nav a {
    min-width: 58px;
    padding: 6px 8px;
  }

  h1 {
    font-size: 40px;
  }

  .actions {
    align-items: stretch;
    flex-direction: column;
  }

  .button {
    width: 100%;
  }
}
`);

console.log(`Built ${notes.length} public notes into docs/`);
