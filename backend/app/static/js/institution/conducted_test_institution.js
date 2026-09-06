(function () {
    const rowsEl = document.getElementById("conducted-test-rows");
    if (!rowsEl) return;

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function formatDate(value) {
        if (!value) return "—";
        return new Date(value).toLocaleString();
    }

    async function loadList() {
        const response = await fetch("/api/institution/conducted-tests/");
        if (!response.ok) {
            rowsEl.innerHTML = '<tr><td colspan="6" class="admin-table-empty">Could not load conducted tests.</td></tr>';
            return;
        }

        const tests = await response.json();

        if (tests.length === 0) {
            rowsEl.innerHTML = '<tr><td colspan="6" class="admin-table-empty">No conducted tests yet.</td></tr>';
            return;
        }

        rowsEl.innerHTML = tests.map((test) => `
            <tr>
                <td><a href="/institution/conducted-tests/${test.id}">${escapeHtml(test.title)}</a></td>
                <td><span class="cbt-code-badge">${escapeHtml(test.test_code)}</span></td>
                <td><span class="admin-badge admin-badge--${test.status.toLowerCase()}">${escapeHtml(test.status)}</span></td>
                <td>${formatDate(test.scheduled_start_at)}</td>
                <td>${test.duration_minutes} min</td>
                <td><a class="admin-btn admin-btn-secondary admin-btn-sm" href="/institution/conducted-tests/${test.id}">Manage</a></td>
            </tr>
        `).join("");
    }

    loadList();
})();
