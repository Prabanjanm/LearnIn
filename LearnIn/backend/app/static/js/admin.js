/*
    Cross-cutting admin panel behaviors. File-upload handling lives in
    components/upload-widget.js and table search/sort/pagination/bulk
    actions live in components/admin-table.js (both loaded alongside this
    file) - kept separate since each is reused outside plain CRUD pages too.
*/

document.addEventListener("DOMContentLoaded", () => {
    initSidebarToggle();
    initDropdowns();
    initTopbarSearch();
    initFlashToasts();
    initFormSubmitState();
});

/*
    Bottom-right floating toast stack (like a typical "Saved" / "Updated"
    notification) - the single source of save/delete/bulk-action feedback
    across the admin panel. Two ways to trigger one:
      1. Server-rendered flash: a redirect landed with ?success=1 or
         ?bulk_failed=N in the URL - admin/_layout.html queues those into
         window.__adminFlashToasts before this script runs.
      2. Programmatically from JS - e.g. the edit drawer calls
         showAdminToast() directly when a save completes inside the iframe,
         since that flow doesn't do a full page redirect.
*/
function showAdminToast(message, variant = "success") {
    const stack = document.querySelector("[data-toast-stack]");
    if (!stack) return;

    const toast = document.createElement("div");
    toast.className = `admin-toast admin-toast--${variant}`;
    toast.setAttribute("role", "status");

    const icon = document.createElement("span");
    icon.className = "admin-toast-icon";
    icon.innerHTML = variant === "error"
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>';

    const text = document.createElement("span");
    text.className = "admin-toast-message";
    text.textContent = message;

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "admin-toast-close";
    closeBtn.setAttribute("aria-label", "Dismiss");
    closeBtn.innerHTML = "&times;";

    toast.append(icon, text, closeBtn);
    stack.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("admin-toast--visible"));

    let dismissTimer = window.setTimeout(dismiss, 4000);

    function dismiss() {
        window.clearTimeout(dismissTimer);
        toast.classList.remove("admin-toast--visible");
        window.setTimeout(() => toast.remove(), 250);
    }

    closeBtn.addEventListener("click", dismiss);
}

function initFlashToasts() {
    const queued = window.__adminFlashToasts || [];
    queued.forEach(({ message, variant }) => showAdminToast(message, variant));

    if (queued.length && window.history.replaceState) {
        const url = new URL(window.location.href);
        url.searchParams.delete("success");
        url.searchParams.delete("bulk_failed");
        window.history.replaceState({}, "", url.toString());
    }
}

function initSidebarToggle() {
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const shell = document.querySelector(".admin-shell");

    if (!toggle || !shell) return;

    toggle.addEventListener("click", () => {
        shell.classList.toggle("admin-shell--collapsed");
        localStorage.setItem(
            "learnin_admin_sidebar_collapsed",
            shell.classList.contains("admin-shell--collapsed") ? "1" : "0"
        );
    });

    if (localStorage.getItem("learnin_admin_sidebar_collapsed") === "1") {
        shell.classList.add("admin-shell--collapsed");
    }
}

function initDropdowns() {
    const dropdowns = document.querySelectorAll("[data-dropdown]");

    dropdowns.forEach((dropdown) => {
        const toggleBtn = dropdown.querySelector("[data-dropdown-toggle]");
        if (!toggleBtn) return;

        toggleBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = dropdown.classList.contains("admin-dropdown--open");
            dropdowns.forEach((other) => other.classList.remove("admin-dropdown--open"));
            if (!isOpen) dropdown.classList.add("admin-dropdown--open");
        });
    });

    document.addEventListener("click", () => {
        dropdowns.forEach((dropdown) => dropdown.classList.remove("admin-dropdown--open"));
    });
}

function initTopbarSearch() {
    const input = document.querySelector("[data-admin-search-input]");
    const resultsBox = document.querySelector("[data-admin-search-results]");
    if (!input || !resultsBox) return;

    const navLinks = Array.from(document.querySelectorAll(".admin-nav-link"));
    const sections = navLinks.map((link) => ({
        label: link.querySelector(".admin-nav-label")?.textContent.trim() || "",
        href: link.getAttribute("href"),
    }));

    const render = (query) => {
        const q = query.trim().toLowerCase();
        if (!q) {
            resultsBox.hidden = true;
            resultsBox.innerHTML = "";
            return;
        }

        const matches = sections.filter((section) => section.label.toLowerCase().includes(q));

        if (matches.length === 0) {
            resultsBox.innerHTML = '<p class="admin-dropdown-empty">No matching section.</p>';
            resultsBox.hidden = false;
            return;
        }

        resultsBox.innerHTML = matches
            .map((section) => `<a href="${section.href}">${section.label}</a>`)
            .join("");
        resultsBox.hidden = false;
    };

    input.addEventListener("input", () => render(input.value));
    input.addEventListener("focus", () => render(input.value));

    document.addEventListener("click", (event) => {
        if (!event.target.closest("[data-admin-search]")) {
            resultsBox.hidden = true;
        }
    });
}


function initFormSubmitState() {
    document.querySelectorAll("[data-admin-form]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            let hasError = false;

            form.querySelectorAll("[required]").forEach((field) => {
                const wrapper = field.closest(".admin-field");
                const errorEl = wrapper?.querySelector("[data-field-error]");
                const isEmpty = !field.value || !field.value.trim();

                if (isEmpty) {
                    hasError = true;
                    wrapper?.classList.add("admin-field--invalid");
                    if (errorEl) {
                        errorEl.textContent = "This field is required.";
                        errorEl.hidden = false;
                    }
                } else {
                    wrapper?.classList.remove("admin-field--invalid");
                    if (errorEl) errorEl.hidden = true;
                }
            });

            if (hasError) {
                event.preventDefault();
                return;
            }

            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.setAttribute("data-loading", "1");
                submitBtn.disabled = true;
                submitBtn.querySelector("[data-btn-spinner]")?.removeAttribute("hidden");
            }
        });
    });
}
