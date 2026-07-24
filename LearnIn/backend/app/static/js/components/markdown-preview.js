/*
    Small self-contained markdown -> HTML renderer for the blog editor's
    live preview tab. Deliberately not a full CommonMark implementation -
    covers the subset admins actually write (headings, bold/italic, links,
    images, lists, code, paragraphs) without pulling in an external library.
*/

function renderMarkdown(source) {
    const escapeHtml = (text) =>
        text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

    const lines = escapeHtml(source || "").split("\n");
    const htmlBlocks = [];
    let listBuffer = [];
    let listType = null;

    const flushList = () => {
        if (listBuffer.length === 0) return;
        const tag = listType === "ol" ? "ol" : "ul";
        htmlBlocks.push(`<${tag}>${listBuffer.join("")}</${tag}>`);
        listBuffer = [];
        listType = null;
    };

    const inline = (text) =>
        text
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">')
            .replace(/\[([^\]]*)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");

    lines.forEach((rawLine) => {
        const line = rawLine.trim();

        if (!line) {
            flushList();
            return;
        }

        const heading = line.match(/^(#{1,6})\s+(.*)$/);
        if (heading) {
            flushList();
            const level = heading[1].length;
            htmlBlocks.push(`<h${level}>${inline(heading[2])}</h${level}>`);
            return;
        }

        const unordered = line.match(/^[-*]\s+(.*)$/);
        if (unordered) {
            if (listType !== "ul") flushList();
            listType = "ul";
            listBuffer.push(`<li>${inline(unordered[1])}</li>`);
            return;
        }

        const ordered = line.match(/^\d+\.\s+(.*)$/);
        if (ordered) {
            if (listType !== "ol") flushList();
            listType = "ol";
            listBuffer.push(`<li>${inline(ordered[1])}</li>`);
            return;
        }

        flushList();
        htmlBlocks.push(`<p>${inline(line)}</p>`);
    });

    flushList();
    return htmlBlocks.join("\n") || '<p class="markdown-editor-empty">Nothing to preview yet.</p>';
}

function initMarkdownEditors(root = document) {
    root.querySelectorAll("[data-markdown-editor]").forEach((editor) => {
        const tabs = editor.querySelectorAll("[data-markdown-tab]");
        const textarea = editor.querySelector('[data-markdown-pane="write"]');
        const preview = editor.querySelector('[data-markdown-pane="preview"]');

        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const target = tab.getAttribute("data-markdown-tab");

                tabs.forEach((other) => other.classList.remove("markdown-editor-tab--active"));
                tab.classList.add("markdown-editor-tab--active");

                if (target === "preview") {
                    preview.innerHTML = renderMarkdown(textarea.value);
                    preview.hidden = false;
                    textarea.hidden = true;
                } else {
                    textarea.hidden = false;
                    preview.hidden = true;
                }
            });
        });
    });
}

document.addEventListener("DOMContentLoaded", () => initMarkdownEditors());
