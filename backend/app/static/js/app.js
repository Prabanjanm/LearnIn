// Branded loading screen: purely cosmetic cleanup. The overlay already
// fades itself out and stops blocking clicks via CSS alone (see
// .page-loader in animations.css) - this only removes the now-invisible
// element from the DOM afterwards so it doesn't linger in the accessibility
// tree. If this never runs (JS disabled/fails), the page still works.
(function () {
    var loader = document.getElementById("page-loader");
    if (!loader) return;

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion) {
        loader.remove();
        return;
    }

    // Cycle the logo through its 5 expression frames (idle/blink/wink/
    // tilt/return - see app/static/img/brand/loader-*.webp) while the
    // overlay is visible, instead of one static image.
    var logoImg = document.getElementById("page-loader-logo");
    var frames = ["idle", "blink", "wink", "tilt", "return"];
    var frameIndex = 0;
    var frameTimer = logoImg && setInterval(function () {
        frameIndex = (frameIndex + 1) % frames.length;
        logoImg.src = "/static/img/brand/loader-" + frames[frameIndex] + ".webp";
    }, 220);

    // animationend bubbles up from child animations too (the logo's own
    // entrance animation ends well before the overlay's fade-out) - only
    // react to the loader's own fade-out finishing, or the overlay would
    // get removed - and the fade cut short - the moment the logo settles.
    loader.addEventListener("animationend", function (event) {
        if (event.target !== loader || event.animationName !== "page-loader-fade-out") return;
        clearInterval(frameTimer);
        loader.remove();
    });
})();

// Universal broken-image fallback: any <img data-fallback="..."> swaps to
// that (bundled, always-available) illustration exactly once if its real
// source 404s/fails - e.g. a Drive file that's since been removed, or a bad
// upload. The "exactly once" guard (data-fallback-applied) stops an infinite
// loop if the fallback asset itself somehow fails to load.
(function () {
    document.addEventListener(
        "error",
        function (event) {
            var img = event.target;
            if (!img || img.tagName !== "IMG") return;

            var fallback = img.getAttribute("data-fallback");
            if (!fallback || img.dataset.fallbackApplied) return;

            img.dataset.fallbackApplied = "true";
            img.src = fallback;
        },
        true
    );
})();

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

// Universal header search: a live-search overlay backed by the existing
// GET /api/search/?q= JSON endpoint. The form itself still plain-submits to
// /search (the existing results page) with no JS at all, so this overlay is
// a progressive enhancement, not a replacement for working search.
(function () {
    var toggle = document.querySelector("[data-search-toggle]");
    var panel = document.querySelector("[data-search-panel]");
    var closeBtn = panel && panel.querySelector("[data-search-close]");
    var input = panel && panel.querySelector("[data-search-input]");
    var resultsBox = panel && panel.querySelector("[data-search-results]");

    if (!toggle || !panel || !input || !resultsBox) return;

    var debounceTimer = null;
    var currentRequest = null;

    function openPanel() {
        panel.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        window.setTimeout(function () { input.focus(); }, 10);
    }

    function closePanel() {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", function () {
        if (panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", closePanel);
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !panel.hidden) {
            closePanel();
        }
    });

    document.addEventListener("click", function (event) {
        if (!panel.hidden && !panel.contains(event.target) && event.target !== toggle && !toggle.contains(event.target)) {
            closePanel();
        }
    });

    var TYPE_LABELS = {
        exam: "Exam",
        department: "Department",
        subject: "Subject",
        paper: "Paper",
        question: "Question",
        mock_test: "Mock Test",
        resource: "Resource",
        blog: "Blog",
    };

    function renderResults(data) {
        if (!data.results.length) {
            resultsBox.innerHTML = '<p class="nav-search-empty">No results for &ldquo;' + escapeHtml(data.query) + '&rdquo;.</p>';
            resultsBox.hidden = false;
            return;
        }

        var items = data.results.slice(0, 8).map(function (item) {
            var typeLabel = TYPE_LABELS[item.type] || item.type;
            return (
                '<a class="nav-search-result" href="' + item.url + '">' +
                '<span class="nav-search-result-type">' + escapeHtml(typeLabel) + '</span>' +
                '<span class="nav-search-result-title">' + escapeHtml(item.title) + '</span>' +
                "</a>"
            );
        });

        if (data.total > items.length) {
            items.push(
                '<a class="nav-search-view-all" href="/search?q=' + encodeURIComponent(data.query) + '">View all ' + data.total + ' results &rarr;</a>'
            );
        }

        resultsBox.innerHTML = items.join("");
        resultsBox.hidden = false;
    }

    function escapeHtml(value) {
        var div = document.createElement("div");
        div.textContent = value;
        return div.innerHTML;
    }

    input.addEventListener("input", function () {
        var term = input.value.trim();

        window.clearTimeout(debounceTimer);

        if (!term) {
            resultsBox.hidden = true;
            resultsBox.innerHTML = "";
            return;
        }

        debounceTimer = window.setTimeout(function () {
            if (currentRequest) currentRequest.abort();
            currentRequest = new AbortController();

            fetch("/api/search/?q=" + encodeURIComponent(term), { signal: currentRequest.signal })
                .then(function (response) { return response.ok ? response.json() : Promise.reject(); })
                .then(renderResults)
                .catch(function (err) {
                    if (err && err.name === "AbortError") return;
                });
        }, 250);
    });
})();

// Account forms (login/signup/profile/change-password): disable the submit
// button and swap its label on submit so a slow request or an impatient
// double-click can't fire the same form twice.
(function () {
    var forms = document.querySelectorAll("[data-account-form]");

    forms.forEach(function (form) {
        form.addEventListener("submit", function () {
            var button = form.querySelector("button[type=submit]");
            if (!button || button.disabled) return;

            button.disabled = true;
            var waitLabel = button.getAttribute("data-submit-label");
            button.textContent = waitLabel ? "Please wait…" : button.textContent;
        });
    });
})();

// Password show/hide toggles (login, signup, ...): each button only ever
// controls the password input in its own .password-input-wrapper, so any
// number of independent toggles can exist on one page (e.g. a future
// Password + Confirm Password pair) without interfering with each other.
(function () {
    var toggles = document.querySelectorAll("[data-password-toggle]");

    toggles.forEach(function (toggle) {
        var wrapper = toggle.closest(".password-input-wrapper");
        var input = wrapper && wrapper.querySelector("input");
        if (!input) return;

        toggle.addEventListener("click", function () {
            var isVisible = input.type === "text";

            input.type = isVisible ? "password" : "text";
            toggle.setAttribute("aria-pressed", String(!isVisible));
            toggle.setAttribute("aria-label", isVisible ? "Show password" : "Hide password");
        });
    });
})();

// Subtle fade/slide-in for `.reveal` sections as they enter the viewport.
// Progressive enhancement only: elements are visible by default (see
// animations.css) - the hidden starting state is added here, right before
// observing, so a JS failure or prefers-reduced-motion never leaves
// content invisible.
(function () {
    var sections = document.querySelectorAll(".reveal");
    if (!sections.length) return;

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || !("IntersectionObserver" in window)) return;

    var observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.remove("reveal--pending");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );

    sections.forEach(function (section) {
        section.classList.add("reveal--pending");
        observer.observe(section);
    });
})();

// Count-up animation for the homepage stats band. Progressive enhancement
// only: the server already renders the real final value (e.g. "54+"), so a
// JS failure, reduced-motion preference, or no IntersectionObserver support
// just leaves that correct, real, backend-supplied number showing - nothing
// here can make a stat display wrong, fake, or blank.
(function () {
    var counters = document.querySelectorAll("[data-count-to]");
    if (!counters.length) return;

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function animateCount(el) {
        var target = parseInt(el.getAttribute("data-count-to"), 10);
        var suffix = el.getAttribute("data-count-suffix") || "";

        // No real value, reduced-motion, or no rAF support: leave the
        // server-rendered final number exactly as it already is.
        if (!target || reduceMotion || !("requestAnimationFrame" in window)) return;

        var duration = 1800;
        var start = null;

        function step(timestamp) {
            if (start === null) start = timestamp;
            var progress = Math.min((timestamp - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            var value = Math.round(eased * target);
            el.textContent = value.toLocaleString() + suffix;

            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = target.toLocaleString() + suffix;
            }
        }

        el.textContent = "0" + suffix;
        window.requestAnimationFrame(step);
    }

    if (!("IntersectionObserver" in window)) return;

    // Animates once per page load: unobserve immediately after the first
    // intersection, so scrolling away and back never restarts the count.
    var observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCount(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.4 }
    );

    counters.forEach(function (el) { observer.observe(el); });
})();

// Navbar "Exams" mega-menu: a <details> panel (matching the existing
// nav-account pattern - native, keyboard/touch accessible with zero extra
// JS for open/close) whose menu is filled from the real, already-public
// GET /api/exams/ list the first time it's opened, then cached in memory
// so re-opening never re-fetches. Never a hardcoded/fake exam list.
(function () {
    var dropdown = document.querySelector("[data-nav-exams-dropdown]");
    var menu = dropdown && dropdown.querySelector("[data-nav-exams-menu]");
    if (!dropdown || !menu) return;

    var loaded = false;

    dropdown.addEventListener("toggle", function () {
        if (!dropdown.open || loaded) return;
        loaded = true;

        fetch("/api/exams/")
            .then(function (response) { return response.ok ? response.json() : Promise.reject(); })
            .then(function (exams) {
                if (!exams.length) {
                    menu.innerHTML = '<p class="nav-dropdown-empty">No exams published yet.</p>';
                    return;
                }
                var html = exams.map(function (exam) {
                    return '<a href="/' + exam.slug + '" class="nav-dropdown-item">' +
                        '<span class="nav-dropdown-item-code">' + exam.code + '</span>' +
                        '<span>' + exam.name + '</span>' +
                        '</a>';
                }).join("");
                html += '<a href="/exams" class="nav-dropdown-viewall">View all exams &rarr;</a>';
                menu.innerHTML = html;
            })
            .catch(function () {
                loaded = false;
                menu.innerHTML = '<p class="nav-dropdown-empty">Couldn\'t load exams - <a href="/exams">view all exams</a>.</p>';
            });
    });

    // Close the menu on an outside click, same expectation set by the
    // native nav-account <details> elsewhere in the navbar.
    document.addEventListener("click", function (event) {
        if (dropdown.open && !dropdown.contains(event.target)) {
            dropdown.open = false;
        }
    });
})();

// Hero heading typing animation: continuously types the same text out,
// pauses, deletes it, pauses, and retypes it - one repeated phrase, never
// a fake multi-message carousel - purely decorative, so if JS never runs
// the static text in data-typing-text already sits in the DOM as a
// fallback and nothing is lost.
(function () {
    var el = document.querySelector("[data-typing-text]");
    if (!el) return;

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var text = el.getAttribute("data-typing-text") || el.textContent;

    if (reduceMotion) {
        el.textContent = text;
        return;
    }

    el.textContent = "";
    el.classList.add("typing-caret");

    var TYPE_SPEED = 45;
    var DELETE_SPEED = 30;
    var HOLD_FULL = 1800;
    var HOLD_EMPTY = 500;

    var i = 0;
    function typeNext() {
        i += 1;
        el.textContent = text.slice(0, i);
        if (i < text.length) {
            window.setTimeout(typeNext, TYPE_SPEED);
        } else {
            window.setTimeout(deleteNext, HOLD_FULL);
        }
    }
    function deleteNext() {
        i -= 1;
        el.textContent = text.slice(0, i);
        if (i > 0) {
            window.setTimeout(deleteNext, DELETE_SPEED);
        } else {
            window.setTimeout(typeNext, HOLD_EMPTY);
        }
    }
    window.setTimeout(typeNext, 300);
})();
