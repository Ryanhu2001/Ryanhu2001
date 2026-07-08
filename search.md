---
layout: default
title: Search
navbar_title: Search
permalink: /search/
pagefind: true
---

<div class="row">
    <div class="col-lg-10 mx-auto">
        <section class="search-page bg-white shadow-sm rounded-xl p-4 p-md-5">
            <div class="search-page-header">
                <h1 class="mb-2">Search</h1>
                <p class="text-muted mb-0">
                    Full-site search across wiki notes and paper reading entries.
                </p>
            </div>
            <div id="pagefind-search" class="site-search-box">
                <pagefind-config
                    bundle-path="{{ '/pagefind/' | relative_url }}"
                    base-url="{{ site.baseurl }}/"
                    excerpt-length="30"
                    lang="zh-CN"></pagefind-config>
                <pagefind-input placeholder="搜索 wiki、论文笔记、关键词..." autofocus></pagefind-input>
                <pagefind-summary></pagefind-summary>
                <pagefind-results show-images="false"></pagefind-results>
            </div>
        </section>
    </div>
</div>
