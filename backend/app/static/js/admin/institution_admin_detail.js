(function () {
    const root = document.getElementById("institution-detail");
    if (!root) return;

    const institutionId = root.dataset.institutionId;
    const userRowsEl = document.getElementById("institution-user-rows");
    const toggle = document.getElementById("conducted-test-toggle");

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    async function loadUsers() {
        const response = await fetch(`/api/admin/institutions/${institutionId}/users`);
        if (!response.ok) {
            userRowsEl.innerHTML = '<tr><td colspan="4" class="admin-table-empty">Could not load users.</td></tr>';
            return;
        }

        const users = await response.json();

        if (users.length === 0) {
            userRowsEl.innerHTML = '<tr><td colspan="4" class="admin-table-empty">No users yet.</td></tr>';
            return;
        }

        userRowsEl.innerHTML = users.map((user) => `
            <tr>
                <td>${escapeHtml(user.email)}</td>
                <td>${escapeHtml(user.full_name || "—")}</td>
                <td>${user.is_active ? "Active" : "Deactivated"}</td>
                <td>
                    ${user.is_active ? `<button type="button" class="admin-btn admin-btn-danger admin-btn-sm" data-deactivate="${user.id}">Deactivate</button>` : ""}
                </td>
            </tr>
        `).join("");

        userRowsEl.querySelectorAll("[data-deactivate]").forEach((button) => {
            button.addEventListener("click", async () => {
                if (!window.confirm("Deactivate this institution user? They will no longer be able to log in.")) return;
                await fetch(`/api/admin/institutions/${institutionId}/users/${button.dataset.deactivate}/deactivate`, { method: "POST" });
                loadUsers();
            });
        });
    }

    if (toggle) {
        toggle.addEventListener("change", async () => {
            const response = await fetch(
                `/api/admin/institutions/${institutionId}/conducted-test-feature?enabled=${toggle.checked}`,
                { method: "POST" }
            );
            if (!response.ok) {
                toggle.checked = !toggle.checked;
                window.alert("Could not update the Conducted Test feature flag.");
            }
        });
    }

    root.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const action = button.dataset.action;
            const confirmMessage = button.dataset.confirm;
            if (confirmMessage && !window.confirm(confirmMessage)) return;

            const response = await fetch(`/api/admin/institutions/${institutionId}/${action}`, { method: "POST" });
            if (response.ok) {
                window.location.reload();
            } else {
                const data = await response.json();
                window.alert(data.detail || "Action failed.");
            }
        });
    });

    const userForm = document.getElementById("institution-user-form");
    const userFormError = document.getElementById("institution-user-form-error");

    if (userForm) {
        userForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            userFormError.hidden = true;

            const payload = {
                email: document.getElementById("user_email").value.trim(),
                full_name: document.getElementById("user_full_name").value.trim() || null,
                password: document.getElementById("user_password").value,
            };

            const response = await fetch(`/api/admin/institutions/${institutionId}/users`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const data = await response.json();
                userFormError.textContent = data.detail || "Could not create this user.";
                userFormError.hidden = false;
                return;
            }

            userForm.reset();
            loadUsers();
        });
    }

    loadUsers();
})();
