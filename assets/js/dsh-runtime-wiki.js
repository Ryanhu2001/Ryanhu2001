(function () {
  "use strict";

  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeLabel = document.querySelector("[data-theme-label]");
  const progressBar = document.querySelector("[data-reading-progress]");
  const themeKey = "dsh-runtime-theme";

  function appendTocLabel(link, label, title) {
    const number = document.createElement("strong");
    const text = document.createElement("span");

    number.textContent = label;
    text.textContent = title;
    link.append(number, text);
  }

  function headingParts(heading, pattern, fallbackLabel) {
    const text = heading.textContent.trim();
    const match = text.match(pattern);
    return match ? [match[1], match[2]] : [fallbackLabel, text];
  }

  function buildArticleToc() {
    const article = document.querySelector("[data-dsh-article]");
    const toc = document.querySelector("[data-article-toc]");
    if (!article || !toc) return;

    const loading = toc.querySelector(".article-toc__loading");
    const headings = Array.from(article.querySelectorAll("h2[id], h3[id]"));
    let currentPart = null;
    let currentList = null;

    headings.forEach(function (heading) {
      if (heading.tagName === "H2") {
        const parts = headingParts(heading, /^(Part\s+\d+)\s*[｜|]\s*(.+)$/i, "Part");
        const group = document.createElement("div");
        const link = document.createElement("a");

        group.className = "toc-part";
        link.className = "toc-part__heading";
        link.href = "#" + heading.id;
        appendTocLabel(link, parts[0], parts[1]);

        currentList = document.createElement("ol");
        group.append(link, currentList);
        toc.append(group);
        currentPart = group;
        return;
      }

      if (!currentPart || !currentList) return;

      const parts = headingParts(heading, /^(\d+\.\d+)\s+(.+)$/, "小节");
      const item = document.createElement("li");
      const link = document.createElement("a");

      link.href = "#" + heading.id;
      appendTocLabel(link, parts[0], parts[1]);
      item.append(link);
      currentList.append(item);
    });

    if (loading) loading.remove();
  }

  function applyTheme(theme, persist) {
    const nextTheme = theme === "light" ? "light" : "dark";
    const targetLabel = nextTheme === "dark" ? "切换到浅色主题" : "切换到深色主题";

    root.dataset.theme = nextTheme;
    if (themeToggle) themeToggle.setAttribute("aria-label", targetLabel);
    if (themeLabel) themeLabel.textContent = targetLabel;

    if (persist) {
      try {
        localStorage.setItem(themeKey, nextTheme);
      } catch (error) {
        // The selected theme still applies when storage is unavailable.
      }
    }
  }

  applyTheme(root.dataset.theme, false);
  buildArticleToc();

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      applyTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
    });
  }

  window.addEventListener("storage", function (event) {
    if (event.key === themeKey && event.newValue) applyTheme(event.newValue, false);
  });

  let progressFrame = 0;

  function updateReadingProgress() {
    progressFrame = 0;
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const value = scrollable > 0 ? Math.min(1, Math.max(0, window.scrollY / scrollable)) : 0;
    if (progressBar) progressBar.style.setProperty("--reading-progress", value.toFixed(4));
  }

  function scheduleProgressUpdate() {
    if (progressFrame) return;
    progressFrame = window.requestAnimationFrame(updateReadingProgress);
  }

  window.addEventListener("scroll", scheduleProgressUpdate, { passive: true });
  window.addEventListener("resize", scheduleProgressUpdate, { passive: true });
  updateReadingProgress();

  const diagramDialog = document.querySelector("[data-diagram-dialog]");
  const diagramFrame = diagramDialog && diagramDialog.querySelector("[data-diagram-frame]");
  const diagramTitle = diagramDialog && diagramDialog.querySelector("[data-diagram-dialog-title]");
  const diagramLoading = diagramDialog && diagramDialog.querySelector("[data-diagram-loading]");
  const diagramClose = diagramDialog && diagramDialog.querySelector("[data-diagram-close]");
  const diagramTriggers = Array.from(document.querySelectorAll("[data-diagram-open]"));
  let lastDiagramTrigger = null;

  function unloadDiagram() {
    if (diagramFrame) diagramFrame.removeAttribute('src');
    if (diagramLoading) diagramLoading.hidden = false;
    document.body.classList.remove("has-open-dialog");
  }

  function closeDiagram() {
    if (!diagramDialog) return;
    if (typeof diagramDialog.close === "function" && diagramDialog.open) {
      diagramDialog.close();
      return;
    }
    diagramDialog.removeAttribute("open");
    unloadDiagram();
    if (lastDiagramTrigger) lastDiagramTrigger.focus();
  }

  function openDiagram(trigger) {
    if (!diagramDialog || !diagramFrame) return;
    const source = trigger.dataset.diagramSrc;
    if (!source) return;

    lastDiagramTrigger = trigger;
    if (diagramTitle) diagramTitle.textContent = trigger.dataset.diagramTitle || "图解";
    if (diagramLoading) diagramLoading.hidden = false;
    diagramFrame.setAttribute("title", trigger.dataset.diagramTitle || "DeepSeek Harness 中文辅助图");
    diagramFrame.setAttribute("src", source);
    document.body.classList.add("has-open-dialog");

    if (typeof diagramDialog.showModal === "function") diagramDialog.showModal();
    else diagramDialog.setAttribute("open", "");
  }

  diagramTriggers.forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      openDiagram(trigger);
    });
  });

  if (diagramFrame) {
    diagramFrame.addEventListener("load", function () {
      if (diagramFrame.hasAttribute("src") && diagramLoading) diagramLoading.hidden = true;
    });
  }

  if (diagramClose) diagramClose.addEventListener("click", closeDiagram);

  if (diagramDialog) {
    diagramDialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      closeDiagram();
    });
    diagramDialog.addEventListener("close", function () {
      unloadDiagram();
      if (lastDiagramTrigger) lastDiagramTrigger.focus();
    });
    diagramDialog.addEventListener("click", function (event) {
      if (event.target === diagramDialog) closeDiagram();
    });
  }
}());
