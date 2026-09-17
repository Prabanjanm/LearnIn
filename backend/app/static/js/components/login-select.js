/*
    Student vs. Institution picker on the /login page: two cards sit
    front-side-up until one is clicked, then it flips (3D rotateY) to
    reveal that role's own login form while the other card steps aside.
    "Choose a different account" flips back to the two-card picker.

    Also honors a `?as=institution` query param (used by the old
    /institution/login link so it still lands the visitor straight on the
    institution form instead of the picker) and a data-active-role
    attribute the server sets after a failed login, so the card that just
    failed re-opens with its error already showing instead of resetting to
    the picker.
*/

function initLoginSelect() {
    const container = document.querySelector("[data-login-select]");
    if (!container) return;

    const cards = container.querySelectorAll("[data-flip-card]");

    function flipTo(card) {
        cards.forEach((other) => {
            if (other === card) {
                other.classList.add("is-flipped");
                other.classList.remove("is-collapsed");
            } else {
                other.classList.remove("is-flipped");
                other.classList.add("is-collapsed");
            }
        });
    }

    function reset() {
        cards.forEach((card) => {
            card.classList.remove("is-flipped", "is-collapsed");
        });
    }

    cards.forEach((card) => {
        const trigger = card.querySelector("[data-flip-trigger]");
        if (trigger) {
            trigger.addEventListener("click", () => flipTo(card));
            trigger.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    flipTo(card);
                }
            });
        }

        card.querySelectorAll("[data-flip-back]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                reset();
            });
        });
    });

    const activeRole = container.getAttribute("data-active-role");
    const queryRole = new URLSearchParams(window.location.search).get("as");
    const initialRole = activeRole || queryRole;

    if (initialRole === "student" || initialRole === "institution") {
        const initialCard = container.querySelector(`[data-flip-card="${initialRole}"]`);
        if (initialCard) flipTo(initialCard);
    }
}

document.addEventListener("DOMContentLoaded", initLoginSelect);
