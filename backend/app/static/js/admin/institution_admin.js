(function () {
    const rowsEl = document.getElementById("institution-rows");
    if (!rowsEl) return;

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    async function loadList() {
        const response = await fetch("/api/admin/institutions/");
        if (!response.ok) {
            rowsEl.innerHTML = '<tr><td colspan="4" class="admin-table-empty">Could not load institutions.</td></tr>';
            return;
        }

        const institutions = await response.json();

        if (institutions.length === 0) {
            rowsEl.innerHTML = '<tr><td colspan="4" class="admin-table-empty">No institutions yet.</td></tr>';
            return;
        }

        rowsEl.innerHTML = institutions.map((institution) => `
            <tr>
                <td><a href="/admin/institutions/${institution.id}">${escapeHtml(institution.name)}</a></td>
                <td><span class="admin-badge admin-badge--${institution.status.toLowerCase()}">${escapeHtml(institution.status)}</span></td>
                <td>${institution.conducted_test_enabled ? "Enabled" : "Disabled"}</td>
                <td><a class="admin-btn admin-btn-secondary admin-btn-sm" href="/admin/institutions/${institution.id}">Manage</a></td>
            </tr>
        `).join("");
    }

    loadList();
})();
