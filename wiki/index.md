---
layout: default
title: Wiki
navbar_title: Wiki
permalink: /wiki/
---

{% assign notes = site.pages | where: "public", true | sort: "date" | reverse %}

<div class="row">
    <div class="col-lg-10 mx-auto">
        <div class="bg-white shadow-sm rounded-xl p-4 p-md-5">
            <h1 class="mb-3">Wiki</h1>
            <p class="text-muted mb-4">
                Selected notes from my Obsidian vault.
            </p>

            <div class="wiki-list">
                {% for note in notes %}
                <article class="wiki-list-item">
                    <h2 class="h5 mb-1">
                        <a href="{{ note.url | relative_url }}">{{ note.title }}</a>
                    </h2>
                    {% if note.description %}
                    <p class="text-muted mb-1">{{ note.description }}</p>
                    {% endif %}
                    {% if note.date %}
                    <div class="small text-muted">{{ note.date | date: "%Y-%m-%d" }}</div>
                    {% endif %}
                </article>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
