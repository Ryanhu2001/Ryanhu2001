(function () {
    var content = document.querySelector(".blog-content");
    if (!content) return;

    var navbarHeight = 88;
    var article = document.querySelector(".wiki-note-card");

    function initReadingSurface() {
        if (!article || !article.hasAttribute("data-reading-surface")) return;

        var nodes = Array.prototype.slice.call(content.childNodes);
        var fragment = document.createDocumentFragment();
        var section = null;
        var sectionIndex = -1;

        nodes.forEach(function (node) {
            var startsSection = node.nodeType === 1 && node.tagName === "H1";

            if (!section && node.nodeType === 3 && !node.textContent.trim()) return;

            if (startsSection || !section) {
                sectionIndex += 1;
                section = document.createElement("section");
                section.className = sectionIndex === 0
                    ? "reading-surface-section reading-surface-hero"
                    : "reading-surface-section reading-surface-doc";
                fragment.appendChild(section);
            }

            section.appendChild(node);
        });

        content.appendChild(fragment);

        var kicker = article.getAttribute("data-kicker");
        if (kicker) {
            Array.prototype.slice.call(content.querySelectorAll(".reading-surface-doc > h1")).forEach(function (h1) {
                var label = document.createElement("p");
                label.className = "doc-kicker";
                label.textContent = kicker;
                h1.parentNode.insertBefore(label, h1);
            });
        }
    }

    initReadingSurface();

    var headings = Array.prototype.slice.call(content.querySelectorAll("h1, h2, h3"));
    var tocHeadings = article && article.hasAttribute("data-reading-surface")
        ? Array.prototype.slice.call(content.querySelectorAll("h1, h2"))
        : headings;

    function slugify(text, fallback) {
        var slug = String(text || "")
            .trim()
            .toLowerCase()
            .replace(/<[^>]+>/g, "")
            .replace(/&[a-z0-9#]+;/g, "")
            .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
            .replace(/^-+|-+$/g, "");
        return slug || fallback;
    }

    function ensureHeadingIds() {
        var seen = {};
        headings.forEach(function (heading, index) {
            var base = heading.id || slugify(heading.textContent, "section-" + (index + 1));
            var unique = base;
            var count = 2;

            while (seen[unique] || document.getElementById(unique)) {
                if (heading.id === unique) break;
                unique = base + "-" + count;
                count += 1;
            }

            heading.id = unique;
            seen[unique] = true;
            heading.style.scrollMarginTop = navbarHeight + "px";
        });
    }

    function initAnchors() {
        if (!window.anchors) return;

        window.anchors.options = {
            visible: "hover",
            placement: "left",
            icon: "#",
            class: "heading-anchor"
        };
        window.anchors.add(".blog-content h2, .blog-content h3, .blog-content h4");
    }

    function manualToc(tocList) {
        tocHeadings.forEach(function (heading) {
            var link = document.createElement("a");
            link.href = "#" + heading.id;
            link.textContent = heading.textContent;
            link.className = "toc-link toc-" + heading.tagName.toLowerCase();
            link.addEventListener("click", function (event) {
                event.preventDefault();
                window.scrollTo({
                    top: heading.offsetTop - navbarHeight,
                    behavior: "smooth"
                });
                history.pushState(null, "", "#" + heading.id);
            });
            tocList.appendChild(link);
        });

        function updateActive() {
            var scrollPos = window.scrollY + navbarHeight + 16;
            var current = null;
            tocHeadings.forEach(function (heading) {
                if (heading.offsetTop <= scrollPos) {
                    current = heading.id;
                }
            });
            Array.prototype.slice.call(tocList.querySelectorAll("a")).forEach(function (link) {
                link.classList.toggle("toc-active", link.getAttribute("href") === "#" + current);
            });
        }

        window.addEventListener("scroll", updateActive, { passive: true });
        updateActive();
    }

    function initToc() {
        var tocNav = document.getElementById("blog-toc");
        var tocList = document.querySelector(".blog-toc-list");
        if (!tocNav || !tocList) return;

        if (tocHeadings.length === 0) {
            tocNav.hidden = true;
            return;
        }

        if (window.tocbot) {
            var isReadingSurface = article && article.hasAttribute("data-reading-surface");
            window.tocbot.init({
                tocSelector: ".blog-toc-list",
                contentSelector: ".blog-content",
                headingSelector: isReadingSurface ? "h1, h2" : "h1, h2, h3",
                hasInnerContainers: true,
                orderedList: false,
                collapseDepth: 6,
                headingsOffset: navbarHeight + 12,
                scrollSmooth: true,
                scrollSmoothOffset: -navbarHeight,
                listClass: "toc-list",
                listItemClass: "toc-list-item",
                linkClass: "toc-link",
                activeLinkClass: "toc-active"
            });
            return;
        }

        manualToc(tocList);
    }

    function initMobileToc() {
        var details = document.querySelector(".mobile-toc");
        var container = document.getElementById("blog-toc-list-mobile");
        var source = document.getElementById("blog-toc-list");
        if (!details || !container) return;
        if (tocHeadings.length === 0 || !source || !source.innerHTML.trim()) {
            details.hidden = true;
            return;
        }
        container.innerHTML = source.innerHTML;
        container.addEventListener("click", function (event) {
            if (event.target.closest("a")) details.removeAttribute("open");
        });
    }

    function initTocToggle() {
        var wrapper = document.querySelector(".blog-layout-wrapper");
        var toggle = document.getElementById("blog-toc-toggle");
        if (!wrapper || !toggle) return;

        var storageKey = "personal-wiki:toc-collapsed";

        function setCollapsed(collapsed) {
            wrapper.classList.toggle("toc-collapsed", collapsed);
            toggle.setAttribute("aria-expanded", String(!collapsed));
            toggle.setAttribute("aria-label", collapsed ? "展开目录" : "收起目录");
            toggle.title = collapsed ? "展开目录" : "收起目录";
        }

        var initialState = false;
        try {
            initialState = window.localStorage.getItem(storageKey) === "true";
        } catch (error) {
            initialState = false;
        }
        setCollapsed(initialState);

        toggle.addEventListener("click", function () {
            var collapsed = !wrapper.classList.contains("toc-collapsed");
            setCollapsed(collapsed);
            try {
                window.localStorage.setItem(storageKey, String(collapsed));
            } catch (error) {
                // The toggle still works when storage is unavailable.
            }
        });
    }

    function initImageZoom() {
        var images = Array.prototype.slice.call(content.querySelectorAll("img:not(.no-zoom)"));
        if (images.length === 0) return;

        var viewer = document.createElement("div");
        viewer.className = "image-zoom-viewer";
        viewer.hidden = true;
        viewer.setAttribute("role", "dialog");
        viewer.setAttribute("aria-modal", "true");
        viewer.setAttribute("aria-label", "图片查看器");
        viewer.setAttribute("aria-hidden", "true");
        viewer.innerHTML = [
            '<div class="image-zoom-stage">',
            '  <div class="image-zoom-canvas">',
            '    <img class="image-zoom-preview" alt="">',
            "  </div>",
            "</div>",
            '<div class="image-zoom-toolbar" role="toolbar" aria-label="图片缩放工具">',
            '  <button type="button" data-zoom-action="out" aria-label="缩小图片">−</button>',
            '  <output class="image-zoom-level" aria-live="polite">100%</output>',
            '  <button type="button" data-zoom-action="in" aria-label="放大图片">+</button>',
            '  <button type="button" class="image-zoom-text-button" data-zoom-action="actual" aria-label="按原始像素尺寸显示">1:1</button>',
            '  <button type="button" class="image-zoom-text-button" data-zoom-action="fit">适应</button>',
            '  <button type="button" class="image-zoom-close" data-zoom-action="close" aria-label="关闭图片查看器">×</button>',
            "</div>",
            '<div class="image-zoom-hint">滚轮或双指连续缩放 · 拖动查看 · 双击放大 · Esc 关闭</div>'
        ].join("");
        document.body.appendChild(viewer);

        var stage = viewer.querySelector(".image-zoom-stage");
        var canvas = viewer.querySelector(".image-zoom-canvas");
        var preview = viewer.querySelector(".image-zoom-preview");
        var toolbar = viewer.querySelector(".image-zoom-toolbar");
        var zoomLevel = viewer.querySelector(".image-zoom-level");
        var closeButton = viewer.querySelector(".image-zoom-close");
        var activeImage = null;
        var scale = 1;
        var fitScale = 1;
        var offsetX = 0;
        var offsetY = 0;
        var pointers = new Map();
        var dragStart = null;
        var pinchStart = null;
        var maximumScale = 8192;

        function renderZoom() {
            canvas.style.transform = "translate3d(" + offsetX + "px, " + offsetY + "px, 0)";
            preview.style.width = preview.naturalWidth
                ? preview.naturalWidth * scale + "px"
                : "auto";
            zoomLevel.textContent = Math.round(scale * 100) + "%";
        }

        function calculateFitScale() {
            if (!preview.naturalWidth || !preview.naturalHeight) return 1;
            var horizontalPadding = stage.clientWidth < 576 ? 24 : 72;
            var verticalPadding = stage.clientWidth < 576 ? 170 : 96;
            var availableWidth = Math.max(1, stage.clientWidth - horizontalPadding);
            var availableHeight = Math.max(1, stage.clientHeight - verticalPadding);
            return Math.min(
                availableWidth / preview.naturalWidth,
                availableHeight / preview.naturalHeight,
                1
            );
        }

        function clampScale(nextScale) {
            var minimumScale = Math.max(fitScale * 0.2, 0.01);
            return Math.max(minimumScale, Math.min(nextScale, maximumScale));
        }

        function zoomAt(nextScale, clientX, clientY) {
            nextScale = clampScale(nextScale);
            if (!Number.isFinite(nextScale) || nextScale === scale) return;

            var rect = stage.getBoundingClientRect();
            var anchorX = (typeof clientX === "number" ? clientX : rect.left + rect.width / 2)
                - rect.left - rect.width / 2;
            var anchorY = (typeof clientY === "number" ? clientY : rect.top + rect.height / 2)
                - rect.top - rect.height / 2;
            var ratio = nextScale / scale;

            offsetX = anchorX - (anchorX - offsetX) * ratio;
            offsetY = anchorY - (anchorY - offsetY) * ratio;
            scale = nextScale;
            renderZoom();
        }

        function fitImage() {
            fitScale = calculateFitScale();
            scale = fitScale;
            offsetX = 0;
            offsetY = 0;
            renderZoom();
        }

        function showActualSize() {
            zoomAt(1);
        }

        function closeViewer() {
            if (viewer.hidden) return;
            viewer.hidden = true;
            viewer.setAttribute("aria-hidden", "true");
            document.body.classList.remove("image-zoom-open");
            pointers.clear();
            dragStart = null;
            pinchStart = null;
            stage.classList.remove("is-dragging");
            preview.removeAttribute("src");

            if (activeImage) {
                activeImage.focus({ preventScroll: true });
            }
            activeImage = null;
        }

        function openViewer(image) {
            activeImage = image;
            viewer.hidden = false;
            viewer.setAttribute("aria-hidden", "false");
            document.body.classList.add("image-zoom-open");
            preview.alt = image.alt || "放大的图片";
            preview.onload = fitImage;
            preview.src = image.currentSrc || image.src;

            if (preview.complete && preview.naturalWidth) {
                window.requestAnimationFrame(fitImage);
            }

            closeButton.focus({ preventScroll: true });
        }

        function pointerValues() {
            return Array.from(pointers.values());
        }

        function startDrag(point) {
            dragStart = {
                pointerId: point.pointerId,
                x: point.x,
                y: point.y,
                offsetX: offsetX,
                offsetY: offsetY
            };
            pinchStart = null;
        }

        function startPinch() {
            var points = pointerValues();
            if (points.length < 2) return;

            var first = points[0];
            var second = points[1];
            var midpointX = (first.x + second.x) / 2;
            var midpointY = (first.y + second.y) / 2;
            var rect = stage.getBoundingClientRect();

            pinchStart = {
                distance: Math.hypot(second.x - first.x, second.y - first.y),
                scale: scale,
                contentX: (midpointX - rect.left - rect.width / 2 - offsetX) / scale,
                contentY: (midpointY - rect.top - rect.height / 2 - offsetY) / scale
            };
            dragStart = null;
        }

        function updatePinch() {
            var points = pointerValues();
            if (points.length < 2 || !pinchStart) return;

            var first = points[0];
            var second = points[1];
            var distance = Math.hypot(second.x - first.x, second.y - first.y);
            var midpointX = (first.x + second.x) / 2;
            var midpointY = (first.y + second.y) / 2;
            var rect = stage.getBoundingClientRect();
            var nextScale = clampScale(pinchStart.scale * distance / Math.max(1, pinchStart.distance));

            scale = nextScale;
            offsetX = midpointX - rect.left - rect.width / 2 - pinchStart.contentX * scale;
            offsetY = midpointY - rect.top - rect.height / 2 - pinchStart.contentY * scale;
            renderZoom();
        }

        function finishPointer(event) {
            pointers.delete(event.pointerId);
            if (stage.hasPointerCapture(event.pointerId)) {
                stage.releasePointerCapture(event.pointerId);
            }

            var remaining = pointerValues();
            if (remaining.length >= 2) {
                startPinch();
            } else if (remaining.length === 1) {
                startDrag(remaining[0]);
            } else {
                dragStart = null;
                pinchStart = null;
                stage.classList.remove("is-dragging");
            }
        }

        images.forEach(function (image) {
            image.classList.add("image-zoom-trigger");
            image.setAttribute("role", "button");
            image.setAttribute("tabindex", "0");
            image.setAttribute("aria-label", "查看大图：" + (image.alt || "图片"));
            image.addEventListener("click", function (event) {
                event.preventDefault();
                openViewer(image);
            });
            image.addEventListener("keydown", function (event) {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                openViewer(image);
            });
        });

        toolbar.addEventListener("click", function (event) {
            var button = event.target.closest("[data-zoom-action]");
            if (!button) return;

            var action = button.getAttribute("data-zoom-action");
            if (action === "in") zoomAt(scale * 1.5);
            if (action === "out") zoomAt(scale / 1.5);
            if (action === "actual") showActualSize();
            if (action === "fit") fitImage();
            if (action === "close") closeViewer();
        });

        stage.addEventListener("wheel", function (event) {
            event.preventDefault();
            var multiplier = Math.exp(-event.deltaY * 0.002);
            multiplier = Math.max(0.5, Math.min(2, multiplier));
            zoomAt(scale * multiplier, event.clientX, event.clientY);
        }, { passive: false });

        stage.addEventListener("dblclick", function (event) {
            event.preventDefault();
            zoomAt(scale * 2, event.clientX, event.clientY);
        });

        stage.addEventListener("pointerdown", function (event) {
            if (event.pointerType === "mouse" && event.button !== 0) return;
            event.preventDefault();
            pointers.set(event.pointerId, {
                pointerId: event.pointerId,
                x: event.clientX,
                y: event.clientY
            });
            stage.setPointerCapture(event.pointerId);
            stage.classList.add("is-dragging");

            if (pointers.size >= 2) {
                startPinch();
            } else {
                startDrag(pointerValues()[0]);
            }
        });

        stage.addEventListener("pointermove", function (event) {
            if (!pointers.has(event.pointerId)) return;
            event.preventDefault();
            pointers.set(event.pointerId, {
                pointerId: event.pointerId,
                x: event.clientX,
                y: event.clientY
            });

            if (pointers.size >= 2) {
                updatePinch();
                return;
            }

            if (dragStart && dragStart.pointerId === event.pointerId) {
                offsetX = dragStart.offsetX + event.clientX - dragStart.x;
                offsetY = dragStart.offsetY + event.clientY - dragStart.y;
                renderZoom();
            }
        });

        stage.addEventListener("pointerup", finishPointer);
        stage.addEventListener("pointercancel", finishPointer);

        document.addEventListener("keydown", function (event) {
            if (viewer.hidden) return;

            if (event.key === "Escape") closeViewer();
            if (event.key === "+" || event.key === "=") zoomAt(scale * 1.5);
            if (event.key === "-") zoomAt(scale / 1.5);
            if (event.key === "0") fitImage();
            if (event.key === "1") showActualSize();
        });

        window.addEventListener("resize", function () {
            if (viewer.hidden) return;
            var wasFitted = Math.abs(scale - fitScale) < 0.001;
            fitScale = calculateFitScale();
            if (wasFitted) {
                scale = fitScale;
                offsetX = 0;
                offsetY = 0;
            }
            renderZoom();
        });
    }

    function detectImageSourceKind(img) {
        var manualSource = (img.dataset && img.dataset.source) || "";
        var className = img.className || "";
        var src = (img.getAttribute("src") || img.currentSrc || "").toLowerCase();

        if (manualSource === "generated" || /\bfigure-generated\b/.test(className)) {
            return "generated";
        }
        if (manualSource === "original" || /\bfigure-original\b/.test(className)) {
            return "original";
        }

        var markedAncestor = img.closest(".figure-generated, .figure-original");
        if (markedAncestor) {
            return markedAncestor.classList.contains("figure-generated") ? "generated" : "original";
        }

        return /\.svg(?:$|[?#])/.test(src) ? "generated" : "original";
    }

    function labelImagesBySource() {
        Array.prototype.slice.call(content.querySelectorAll("img")).forEach(function (img) {
            if (img.closest(".image-source-frame") || img.classList.contains("no-source-label")) return;

            var sourceKind = detectImageSourceKind(img);
            var frame = document.createElement("span");
            var badge = document.createElement("span");

            frame.className = "image-source-frame image-source-" + sourceKind;
            frame.setAttribute(
                "data-source-kind",
                sourceKind === "generated" ? "generated" : "original"
            );

            badge.className = "image-source-badge";
            badge.textContent = sourceKind === "generated" ? "自制图解" : "原文图 / 截图";
            frame.appendChild(badge);

            img.parentNode.insertBefore(frame, img);
            frame.appendChild(img);
        });
    }

    function initReadingProgress() {
        var bar = document.querySelector(".reading-progress span");
        var article = document.querySelector(".wiki-note-card");
        if (!bar || !article) return;

        function updateProgress() {
            var start = article.offsetTop - navbarHeight;
            var end = start + article.offsetHeight - window.innerHeight + navbarHeight;
            var ratio = end > start ? (window.scrollY - start) / (end - start) : 1;
            var clamped = Math.max(0, Math.min(1, ratio));
            bar.style.transform = "scaleX(" + clamped + ")";
        }

        window.addEventListener("scroll", updateProgress, { passive: true });
        window.addEventListener("resize", updateProgress);
        updateProgress();
    }

    function wrapTables() {
        Array.prototype.slice.call(content.querySelectorAll("table")).forEach(function (table) {
            if (table.parentElement && table.parentElement.classList.contains("table-scroll")) return;
            var wrapper = document.createElement("div");
            wrapper.className = "table-scroll";
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });
    }

    function markExternalLinks() {
        Array.prototype.slice.call(content.querySelectorAll("a[href^='http']")).forEach(function (link) {
            if (link.hostname === window.location.hostname) return;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
        });
    }

    ensureHeadingIds();
    initToc();
    initMobileToc();
    initTocToggle();
    initAnchors();
    labelImagesBySource();
    initImageZoom();
    initReadingProgress();
    wrapTables();
    markExternalLinks();
})();
