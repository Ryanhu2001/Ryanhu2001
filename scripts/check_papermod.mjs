import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),site=path.join(root,'_site');
const base='/Ryanhu2001/';
const files=['index.html','wiki/Linear Attention.html','wiki/kv-cache/index.html','wiki/rotary-position-embeddings/index.html'];
let checks=0;
for(const file of files){
 const html=fs.readFileSync(path.join(site,file),'utf8');
 assert(!/localhost|127\.0\.0\.1|noindex|nofollow/.test(html.replaceAll('noopener noreferrer',''))&&html.includes('PaperMod'),`Production metadata: ${file}`);
 assert(/<html[^>]+lang=["']?en/.test(html));
 assert(!/\p{Script=Han}/u.test(html),`English article: ${file}`);
 assert.equal((html.match(/<h1\b/g)||[]).length,1);
 assert(!/<a\b[^>]+href=["'][^"']+\.(?:svg|drawio|vsdx|excalidraw)["']/i.test(html),`No source/download clutter: ${file}`);
 assert(html.includes('https://ryanhu2001.github.io/Ryanhu2001/'));
 const current=new URL(file==='index.html'?'':file,'https://ryanhu2001.github.io'+base);
 for(const match of html.matchAll(/(?:src|href)=(?:"([^"]+)"|'([^']+)'|([^\s>]+))/g)){
  const link=match[1]||match[2]||match[3];
  if(link.startsWith('#')||link.startsWith('data:'))continue;
  const resolved=new URL(link,current);
  if(resolved.origin!==current.origin)continue;
  assert(resolved.pathname.startsWith(base),`Link loses base path: ${link}`);
  const relative=decodeURIComponent(resolved.pathname.slice(base.length));
  const target=path.join(site,relative);
  assert(fs.existsSync(target),`Broken local asset/link in ${file}: ${link}`);
 }
 checks+=7;
}
const home=fs.readFileSync(path.join(site,'index.html'),'utf8');
assert.equal((home.match(/class=\"?entry-link/g)||[]).length,3);
assert(home.includes('social-icons')&&home.includes('https://github.com/Ryanhu2001'));
const article=fs.readFileSync(path.join(site,'wiki/Linear Attention.html'),'utf8');
assert(article.includes('hybrid-attention.svg'));
assert(article.includes('katex-mathml')&&article.includes('language-python'));
for(const file of files.slice(1))assert(fs.readFileSync(path.join(site,file),'utf8').includes('data-pagefind-body'));
assert(!/<details[^>]*class=["']?toc[^>]*\bopen\b/.test(article));
assert(!fs.readFileSync(path.join(site,'robots.txt'),'utf8').includes('Disallow: /'));
for(const file of ['wiki/index.html','paper-reading/index.html','pagefind/pagefind.js'])assert(fs.existsSync(path.join(site,file)),`Legacy/search route preserved: ${file}`);
assert(!fs.existsSync(path.join(site,'papermod')));
assert(!fs.existsSync(path.join(site,'diagrams')));
const svg=fs.readFileSync(path.join(site,'assets/wiki/linear-attention/hybrid-attention.svg'),'utf8');
assert(!/<(?:image|foreignObject)\b/.test(svg));
assert(svg.includes('Qwen3.8-Flash-Next')&&svg.includes('Kimi K3'));
console.log(`PaperMod release checks passed (${checks+12} assertions). Legacy routes and Pagefind retained.`);
