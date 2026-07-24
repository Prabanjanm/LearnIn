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
    initAutoDismissToasts();
    initFormSubmitState();
});

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

function initAutoDismissToasts() {
    document.querySelectorAll("[data-auto-dismiss]").forEach((toast) => {
        setTimeout(() => {
            toast.style.transition = "opacity .3s ease";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
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
