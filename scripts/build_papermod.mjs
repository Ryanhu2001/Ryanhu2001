import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const destination=path.join(root,'_site');
if(!fs.existsSync(path.join(destination,'wiki/index.html')))throw Error('Build the legacy Jekyll site first.');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'ryan-papermod-'));
const hugo=process.env.HUGO_BINARY||'hugo';
const version=execFileSync(hugo,['version'],{encoding:'utf8'});
if(!/v0\.165\.0(?:\+|\s|[-/])/.test(version))throw Error(`Expected Hugo 0.165.0; got ${version.trim()}`);
execFileSync(hugo,['--source',path.join(root,'papermod'),'--environment','production','--destination',temporary,'--cacheDir',path.join(temporary,'.cache'),'--minify'],{stdio:'inherit'});
const routes=['index.html','wiki/Linear Attention.html','wiki/kv-cache/index.html','wiki/rotary-position-embeddings/index.html'];
for(const file of routes)if(!fs.existsSync(path.join(temporary,file)))throw Error(`Missing release page: ${file}`);
// Add search-only metadata during composition; keep upstream theme templates unchanged.
for(const file of routes.slice(1)){
 const target=path.join(temporary,file),html=fs.readFileSync(target,'utf8');
 const body=/<div class="post-content md-content">/;
 if(!body.test(html))throw Error(`Cannot find article body for Pagefind: ${file}`);
 fs.writeFileSync(target,html.replace(body,'<div class="post-content md-content" data-pagefind-body>'));
}
if(fs.existsSync(path.join(temporary,'wiki/index.html')))throw Error('Hugo must not replace the legacy wiki index.');
const allowed=new Set(['index.html','404.html','robots.txt','favicon.svg','assets','css','vendor','wiki','page']);
for(const entry of fs.readdirSync(temporary,{withFileTypes:true})){
 if(entry.name==='.cache')continue;
 if(!allowed.has(entry.name))throw Error(`Unexpected Hugo output: ${entry.name}`);
 fs.cpSync(path.join(temporary,entry.name),path.join(destination,entry.name),{recursive:true});
}
console.log('PaperMod homepage and three articles composed with legacy routes.');
