(function () {
    var header = document.querySelector("[data-navbar]");
    var toggle = header && header.querySelector("[data-nav-toggle]");

    if (!header || !toggle) return;

    toggle.addEventListener("click", function () {
        var isOpen = header.hasAttribute("data-nav-open");

        if (isOpen) {
            header.removeAttribute("data-nav-open");
        } else {
            header.setAttribute("data-nav-open", "");
        }

        toggle.setAttribute("aria-expanded", String(!isOpen));
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && header.hasAttribute("data-nav-open")) {
            header.removeAttribute("data-nav-open");
            toggle.setAttribute("aria-expanded", "false");
        }
    });
})();
