(function () {
    const form = document.getElementById("institution-form");
    if (!form) return;

    const errorEl = document.getElementById("institution-form-error");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.hidden = true;

        const payload = {
            name: document.getElementById("name").value.trim(),
            conducted_test_enabled: document.getElementById("conducted_test_enabled").checked,
        };

        try {
            const response = await fetch("/api/admin/institutions/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                errorEl.textContent = data.detail || "Could not create this institution.";
                errorEl.hidden = false;
                return;
            }

            window.location.href = `/admin/institutions/${data.id}`;
        } catch (err) {
            errorEl.textContent = "Something went wrong. Please try again.";
            errorEl.hidden = false;
        }
    });
})();
