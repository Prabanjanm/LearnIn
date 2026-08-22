/*
    Reusable behavior for the generic admin list tables: client-side search,
    sortable columns, pagination, and row checkboxes wired to a bulk-action
    toolbar. One module shared by every entity's list.html instead of
    duplicating table logic per section.
*/

function initAdminTables(root = document) {
    root.querySelectorAll("[data-admin-table]").forEach(initTable);
}

function initTable(table) {
    const wrapper = table.closest("form") || document;
    const pageSize = parseInt(table.getAttribute("data-page-size"), 10) || 10;
    const tbody = table.querySelector("tbody");
    const searchInput = wrapper.querySelector("[data-table-search]");
    const pagination = wrapper.querySelector("[data-pagination]");
    const bulkBar = wrapper.querySelector("[data-bulk-actions]");
    const bulkCount = wrapper.querySelector("[data-bulk-count]");
    const selectAll = table.querySelector("[data-select-all]");
    const bulkActionInput = wrapper.querySelector("[data-bulk-action-input]");
    const bulkForm = wrapper.matches("[data-bulk-form]") ? wrapper : null;
    const filterInputs = Array.from(table.querySelectorAll("[data-col-filter]"));

    const getDataRows = () =>
        Array.from(tbody.querySelectorAll("tr")).filter((row) => row.querySelector("[data-row-checkbox]"));

    let currentPage = 1;
    let sortState = { index: null, dir: null };

    function matchesSearch(row, query) {
        if (!query) return true;
        return row.textContent.toLowerCase().includes(query);
    }

    function matchesColumnFilters(row) {
        return filterInputs.every((input) => {
            const term = input.value.trim().toLowerCase();
            if (!term) return true;

            const index = parseInt(input.getAttribute("data-col-filter"), 10);
            const cell = row.children[index + 1];
            const text = cell ? cell.textContent.trim().toLowerCase() : "";
            return text.includes(term);
        });
    }

    function applyView() {
        const rows = getDataRows();
        const query = (searchInput?.value || "").trim().toLowerCase();
        const matched = rows.filter((row) => matchesSearch(row, query) && matchesColumnFilters(row));

        const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));
        currentPage = Math.min(currentPage, totalPages);

        const start = (currentPage - 1) * pageSize;
        const visible = new Set(matched.slice(start, start + pageSize));

        rows.forEach((row) => {
            row.hidden = !visible.has(row);
        });

        renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
        if (!pagination) return;

        if (totalPages <= 1) {
            pagination.hidden = true;
            pagination.innerHTML = "";
            return;
        }

        pagination.hidden = false;
        const buttons = [];
        for (let page = 1; page <= totalPages; page += 1) {
            buttons.push(
                `<button type="button" data-page="${page}" ${page === currentPage ? "data-active" : ""}>${page}</button>`
            );
        }
        pagination.innerHTML = buttons.join("");

        pagination.querySelectorAll("[data-page]").forEach((btn) => {
            btn.addEventListener("click", () => {
                currentPage = parseInt(btn.getAttribute("data-page"), 10);
                applyView();
            });
        });
    }

    function updateBulkBar() {
        if (!bulkBar) return;
        const checked = table.querySelectorAll("[data-row-checkbox]:checked");
        if (bulkCount) bulkCount.textContent = String(checked.length);
        bulkBar.hidden = checked.length === 0;
    }

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            currentPage = 1;
            applyView();
        });
    }

    filterInputs.forEach((input) => {
        input.addEventListener("input", () => {
            currentPage = 1;
            applyView();
        });
        input.addEventListener("click", (event) => event.stopPropagation());
    });

    table.querySelectorAll("th[data-sortable]").forEach((th) => {
        th.addEventListener("click", () => {
            const index = parseInt(th.getAttribute("data-col-index"), 10);
            const dir = sortState.index === index && sortState.dir === "asc" ? "desc" : "asc";
            sortState = { index, dir };

            table.querySelectorAll("th[data-sortable]").forEach((other) => other.removeAttribute("data-sort-dir"));
            th.setAttribute("data-sort-dir", dir);

            const rows = getDataRows();
            const cellText = (row) => {
                const cell = row.children[index + 1];
                return cell ? cell.textContent.trim().toLowerCase() : "";
            };

            rows.sort((a, b) => {
                const va = cellText(a);
                const vb = cellText(b);
                const na = parseFloat(va);
                const nb = parseFloat(vb);
                let cmp;
                if (!Number.isNaN(na) && !Number.isNaN(nb)) {
                    cmp = na - nb;
                } else {
                    cmp = va.localeCompare(vb);
                }
                return dir === "asc" ? cmp : -cmp;
            });

            rows.forEach((row) => tbody.appendChild(row));
            currentPage = 1;
            applyView();
        });
    });

    if (selectAll) {
        selectAll.addEventListener("change", () => {
            table.querySelectorAll("[data-row-checkbox]").forEach((checkbox) => {
                checkbox.checked = selectAll.checked;
            });
            updateBulkBar();
        });
    }

    table.querySelectorAll("[data-row-checkbox]").forEach((checkbox) => {
        checkbox.addEventListener("change", updateBulkBar);
    });

    if (bulkForm) {
        bulkForm.querySelectorAll("[data-bulk-submit]").forEach((btn) => {
            btn.addEventListener("click", (event) => {
                const action = btn.getAttribute("data-bulk-submit");
                if (bulkActionInput) bulkActionInput.value = action;

                const confirmMessage = btn.getAttribute("data-confirm");
                if (confirmMessage && !window.confirm(confirmMessage)) {
                    event.preventDefault();
                }
            });
        });
    }

    applyView();
    updateBulkBar();
}

document.addEventListener("DOMContentLoaded", () => initAdminTables());
