---
layout: default
title: Paper Reading
navbar_title: Paper Reading
permalink: /paper-reading/
---

{% assign notes = site.pages | where: "public", true | where: "type", "paper-reading" | sort: "created_at" | reverse %}

<div class="row">
    <div class="col-lg-11 mx-auto">
        <section class="paper-reading-panel bg-white shadow-sm rounded-xl p-4 p-md-5" data-paper-reading-index>
            <div class="paper-reading-header">
                <div>
                    <h1 class="mb-2">Paper Reading</h1>
                    <div class="paper-reading-meta">
                        <span data-result-count>{{ notes | size }}</span> notes · sorted by created time
                    </div>
                </div>
                <div class="paper-search-wrap">
                    <i class="fas fa-search" aria-hidden="true"></i>
                    <input
                        type="search"
                        class="paper-search-input"
                        placeholder="Search title, tag, source..."
                        aria-label="Search paper reading notes"
                        data-filter-search>
                </div>
            </div>

            <div class="paper-filter-block" aria-label="Paper reading filters">
                <div class="paper-filter-row">
                    <div class="paper-filter-label">Category</div>
                    <div class="paper-filter-options" data-category-filters></div>
                </div>
                <div class="paper-filter-row">
                    <div class="paper-filter-label">Tag</div>
                    <div class="paper-filter-options" data-tag-filters></div>
                </div>
            </div>

            <div class="wiki-list paper-note-list">
                {% for note in notes %}
                {% capture search_text %}
                    {{ note.title }}
                    {{ note.paper_title }}
                    {{ note.description }}
                    {{ note.category }}
                    {{ note.venue }}
                    {{ note.year }}
                    {% for tag in note.tags %}{{ tag }} {% endfor %}
                {% endcapture %}
                <article
                    class="wiki-list-item paper-note-item"
                    data-category="{{ note.category | default: 'Uncategorized' | escape }}"
                    data-tags="{{ note.tags | join: '|' | escape }}"
                    data-search="{{ search_text | strip_html | downcase | normalize_whitespace | escape }}">
                    <div class="paper-note-topline">
                        {% if note.category %}
                        <span class="paper-note-category">{{ note.category }}</span>
                        {% endif %}
                        {% if note.created_at %}
                        <time class="paper-note-time" datetime="{{ note.created_at }}">
                            {{ note.created_at | date: "%Y-%m-%d %H:%M" }}
                        </time>
                        {% elsif note.date %}
                        <time class="paper-note-time" datetime="{{ note.date }}">
                            {{ note.date | date: "%Y-%m-%d" }}
                        </time>
                        {% endif %}
                    </div>
                    <h2 class="h5 mb-2">
                        <a href="{{ note.url | relative_url }}">{{ note.title }}</a>
                    </h2>
                    {% if note.description %}
                    <p class="text-muted mb-2">{{ note.description }}</p>
                    {% endif %}
                    {% if note.tags %}
                    <div class="paper-note-tags" aria-label="Tags">
                        {% for tag in note.tags %}
                        <span class="paper-note-tag">{{ tag }}</span>
                        {% endfor %}
                    </div>
                    {% endif %}
                </article>
                {% endfor %}
            </div>

            <div class="paper-empty-state" data-empty-state hidden>No matching notes.</div>
        </section>
    </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", function() {
    var root = document.querySelector("[data-paper-reading-index]");
    if (!root) return;

    var items = Array.prototype.slice.call(root.querySelectorAll(".paper-note-item"));
    var searchInput = root.querySelector("[data-filter-search]");
    var categoryWrap = root.querySelector("[data-category-filters]");
    var tagWrap = root.querySelector("[data-tag-filters]");
    var count = root.querySelector("[data-result-count]");
    var emptyState = root.querySelector("[data-empty-state]");
    var activeCategory = "all";
    var activeTag = "all";

    function normalize(value) {
        return String(value || "").trim();
    }

    function increment(map, key) {
        key = normalize(key);
        if (!key) return;
        map.set(key, (map.get(key) || 0) + 1);
    }

    function buildMapFromItems() {
        var categories = new Map();
        var tags = new Map();
        items.forEach(function(item) {
            increment(categories, item.dataset.category || "Uncategorized");
            normalize(item.dataset.tags).split("|").forEach(function(tag) {
                increment(tags, tag);
            });
        });
        return { categories: categories, tags: tags };
    }

    function makeButton(label, value, total, activeValue, onClick) {
        var button = document.createElement("button");
        var labelSpan = document.createElement("span");
        var totalSpan = document.createElement("span");
        button.type = "button";
        button.className = "paper-filter-btn";
        button.dataset.value = value;
        button.setAttribute("aria-pressed", value === activeValue ? "true" : "false");
        labelSpan.textContent = label;
        totalSpan.className = "paper-filter-count";
        totalSpan.textContent = total;
        button.appendChild(labelSpan);
        button.appendChild(totalSpan);
        button.addEventListener("click", onClick);
        return button;
    }

    function renderButtons(container, map, activeValue, onSelect) {
        container.innerHTML = "";
        container.appendChild(makeButton("All", "all", items.length, activeValue, function() {
            onSelect("all");
        }));
        Array.from(map.entries())
            .sort(function(a, b) {
                return a[0].localeCompare(b[0]);
            })
            .forEach(function(entry) {
                container.appendChild(makeButton(entry[0], entry[0], entry[1], activeValue, function() {
                    onSelect(entry[0]);
                }));
            });
    }

    function updatePressed(container, activeValue) {
        Array.prototype.slice.call(container.querySelectorAll("button")).forEach(function(button) {
            button.setAttribute("aria-pressed", button.dataset.value === activeValue ? "true" : "false");
        });
    }

    function itemTags(item) {
        return normalize(item.dataset.tags).split("|").filter(Boolean);
    }

    function applyFilters() {
        var query = normalize(searchInput.value).toLowerCase();
        var visible = 0;

        items.forEach(function(item) {
            var matchesSearch = !query || normalize(item.dataset.search).indexOf(query) !== -1;
            var matchesCategory = activeCategory === "all" || item.dataset.category === activeCategory;
            var matchesTag = activeTag === "all" || itemTags(item).indexOf(activeTag) !== -1;
            var shouldShow = matchesSearch && matchesCategory && matchesTag;
            item.hidden = !shouldShow;
            if (shouldShow) visible += 1;
        });

        count.textContent = visible;
        emptyState.hidden = visible !== 0;
        updatePressed(categoryWrap, activeCategory);
        updatePressed(tagWrap, activeTag);
    }

    var maps = buildMapFromItems();
    renderButtons(categoryWrap, maps.categories, activeCategory, function(value) {
        activeCategory = value;
        applyFilters();
    });
    renderButtons(tagWrap, maps.tags, activeTag, function(value) {
        activeTag = value;
        applyFilters();
    });

    searchInput.addEventListener("input", applyFilters);
    applyFilters();
});
</script>
