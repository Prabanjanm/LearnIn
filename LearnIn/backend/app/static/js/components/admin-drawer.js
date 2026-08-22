/*
    Slide-over drawer used by every admin list page's "Edit" action: opens
    the entity's edit form (rendered bare, via ?embed=1) inside an iframe on
    the right side of the screen instead of navigating away from the list.

    On a successful save, admin/form_saved.html (served instead of the usual
    redirect when the form was submitted with embed=1) posts a
    {type: "admin-drawer-saved"} message from inside the iframe; this
    module listens for it, closes the drawer, and navigates the list page to
    itself with ?success=1 - the same flash-toast mechanism every other save
    path already uses (admin.js's initFlashToasts), so a drawer save gets
    the same "Saved successfully." confirmation instead of silently
    reloading with no feedback at all.
*/

function initAdminDrawer() {
    const overlay = document.querySelector("[data-drawer-overlay]");
    const panel = document.querySelector("[data-drawer-panel]");
    const iframe = document.querySelector("[data-drawer-iframe]");
    const titleEl = document.querySelector("[data-drawer-title]");
    const closeBtn = document.querySelector("[data-drawer-close]");

    if (!overlay || !panel || !iframe) {
        return;
    }

    function openDrawer(url, title) {
        titleEl.textContent = title || "Edit";
        iframe.src = url;
        overlay.hidden = false;
        document.body.classList.add("admin-drawer-open");
        requestAnimationFrame(() => panel.classList.add("admin-drawer-panel--open"));
    }

    function closeDrawer() {
        panel.classList.remove("admin-drawer-panel--open");
        document.body.classList.remove("admin-drawer-open");
        window.setTimeout(() => {
            overlay.hidden = true;
            iframe.src = "about:blank";
        }, 200);
    }

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-drawer-open]");
        if (!trigger) return;

        event.preventDefault();
        openDrawer(trigger.getAttribute("data-drawer-url"), trigger.getAttribute("data-drawer-title"));
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", closeDrawer);
    }

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            closeDrawer();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !overlay.hidden) {
            closeDrawer();
        }
    });

    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        if (event.data && event.data.type === "admin-drawer-saved") {
            closeDrawer();

            const url = new URL(window.location.href);
            url.searchParams.set("success", "1");
            window.location.href = url.toString();
        }
    });
}

document.addEventListener("DOMContentLoaded", initAdminDrawer);
