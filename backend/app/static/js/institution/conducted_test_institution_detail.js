(function () {
    const root = document.getElementById("conducted-test-detail");
    if (!root) return;

    const conductedTestId = root.dataset.conductedTestId;
    const rowsEl = document.getElementById("participant-rows");

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function formatDate(value) {
        if (!value) return "—";
        return new Date(value).toLocaleString();
    }

    async function loadParticipants() {
        const response = await fetch(`/api/institution/conducted-tests/${conductedTestId}/participants`);
        if (!response.ok) {
            rowsEl.innerHTML = '<tr><td colspan="8" class="admin-table-empty">Could not load participants.</td></tr>';
            return;
        }

        const participants = await response.json();

        if (participants.length === 0) {
            rowsEl.innerHTML = '<tr><td colspan="8" class="admin-table-empty">No students have joined yet.</td></tr>';
            return;
        }

        rowsEl.innerHTML = participants.map((row) => `
            <tr>
                <td>${escapeHtml(row.student_name || row.student_email)}</td>
                <td><span class="cbt-code-badge">${escapeHtml(row.result_code)}</span></td>
                <td>${formatDate(row.started_at)}</td>
                <td>${formatDate(row.submitted_at)}</td>
                <td>${row.scored_marks != null ? `${row.scored_marks} / ${row.total_marks}` : "—"}</td>
                <td>${escapeHtml(row.status)}</td>
                <td>${escapeHtml(row.termination_reason || "—")}</td>
                <td>
                    <a class="admin-btn admin-btn-secondary admin-btn-sm" href="/institution/conducted-tests/${conductedTestId}/results/${row.result_code}">View</a>
                    ${row.status === "IN_PROGRESS" ? `<button type="button" class="admin-btn admin-btn-danger admin-btn-sm" data-terminate="${row.student_id}">Terminate</button>` : ""}
                </td>
            </tr>
        `).join("");

        rowsEl.querySelectorAll("[data-terminate]").forEach((button) => {
            button.addEventListener("click", () => terminateAttempt(button.dataset.terminate));
        });
    }

    async function terminateAttempt(studentId) {
        if (!window.confirm("Terminate this student's in-progress attempt? This locks it permanently.")) return;

        await fetch(`/api/institution/conducted-tests/${conductedTestId}/attempts/${studentId}/terminate`, { method: "POST" });
        loadParticipants();
    }

    async function callAction(action) {
        const response = await fetch(`/api/institution/conducted-tests/${conductedTestId}/${action}`, { method: "POST" });
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            window.alert(data.detail || "Action failed.");
        }
    }

    root.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => {
            const action = button.dataset.action;
            const confirmMessage = button.dataset.confirm;

            if (confirmMessage && !window.confirm(confirmMessage)) return;

            if (action === "delete") {
                fetch(`/api/institution/conducted-tests/${conductedTestId}`, { method: "DELETE" }).then((response) => {
                    if (response.ok) window.location.href = "/institution/conducted-tests";
                });
                return;
            }

            callAction(action);
        });
    });

    loadParticipants();
})();
