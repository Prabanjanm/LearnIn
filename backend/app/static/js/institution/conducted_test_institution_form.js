(function () {
    const form = document.getElementById("conducted-test-form");
    if (!form) return;

    const mockTestSelect = document.getElementById("mock_test_id");
    const errorEl = document.getElementById("conducted-test-form-error");

    async function loadMockTests() {
        try {
            const response = await fetch("/api/institution/conducted-tests/available-mock-tests");
            const mockTests = await response.json();

            if (!response.ok || mockTests.length === 0) {
                mockTestSelect.innerHTML = '<option value="">No published mock tests available</option>';
                return;
            }

            mockTestSelect.innerHTML = '<option value="">Select a mock test...</option>' + mockTests.map(
                (mockTest) => `<option value="${mockTest.id}">${mockTest.title} (${mockTest.total_questions} questions)</option>`
            ).join("");
        } catch (err) {
            mockTestSelect.innerHTML = '<option value="">Could not load mock tests</option>';
        }
    }

    function localDatetimeToIso(value) {
        // <input type="datetime-local"> has no timezone of its own - it's
        // interpreted here as the institution user's own browser-local
        // time and converted to a real, timezone-aware instant before
        // it's ever sent to the server, since ConductedTest.scheduled_start_at
        // must be an unambiguous point in time shared by every student.
        const date = new Date(value);
        return date.toISOString();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl.hidden = true;

        const payload = {
            mock_test_id: parseInt(mockTestSelect.value, 10),
            title: document.getElementById("title").value.trim(),
            instructions: document.getElementById("instructions").value.trim() || null,
            duration_minutes: parseInt(document.getElementById("duration_minutes").value, 10),
            scheduled_start_at: localDatetimeToIso(document.getElementById("scheduled_start_at").value),
        };

        try {
            const response = await fetch("/api/institution/conducted-tests/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                errorEl.textContent = data.detail || "Could not create this conducted test.";
                errorEl.hidden = false;
                return;
            }

            window.location.href = `/institution/conducted-tests/${data.id}`;
        } catch (err) {
            errorEl.textContent = "Something went wrong. Please try again.";
            errorEl.hidden = false;
        }
    });

    loadMockTests();
})();
