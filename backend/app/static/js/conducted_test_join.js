(function () {
    const form = document.getElementById("join-test-form");
    if (!form) return;

    const errorEl = document.getElementById("join-test-error");
    const input = document.getElementById("test_code");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.hidden = true;

        const testCode = input.value.trim().toUpperCase();
        if (!testCode) return;

        try {
            const response = await fetch("/api/conducted-tests/join", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ test_code: testCode }),
            });

            const data = await response.json();

            if (!response.ok) {
                errorEl.textContent = data.detail || "Invalid or inactive test code.";
                errorEl.hidden = false;
                return;
            }

            if (data.already_completed) {
                errorEl.textContent = "You have already completed this test - only one attempt is allowed.";
                errorEl.hidden = false;
                return;
            }

            window.location.href = `/conducted-tests/${data.conducted_test_id}`;
        } catch (err) {
            errorEl.textContent = "Something went wrong. Please try again.";
            errorEl.hidden = false;
        }
    });
})();
