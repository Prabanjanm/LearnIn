(function () {
    // Progressive enhancement only - the form works via its Submit button
    // with no JS at all. This just saves a click: changing the exam or
    // department resets the narrower filters below it (a department_id
    // from the old exam wouldn't make sense), then resubmits so the
    // server can render the right department/subject options for the
    // newly selected exam.
    var form = document.querySelector("[data-paper-filters]");
    if (!form) return;

    form.querySelectorAll("select").forEach(function (select) {
        select.addEventListener("change", function () {
            if (select.name === "exam_id") {
                var departmentSelect = form.querySelector('select[name="department_id"]');
                var subjectSelect = form.querySelector('select[name="subject_id"]');
                if (departmentSelect) departmentSelect.value = "";
                if (subjectSelect) subjectSelect.value = "";
            }
            if (select.name === "department_id") {
                var subjectSelect2 = form.querySelector('select[name="subject_id"]');
                if (subjectSelect2) subjectSelect2.value = "";
            }
            form.submit();
        });
    });
})();
