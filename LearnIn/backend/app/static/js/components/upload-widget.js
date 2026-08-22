/*
    Reusable "automatic Drive upload" widget. Wires up every
    .upload-dropzone on the page: click-to-browse, drag & drop, an instant
    local preview, a real upload-progress bar (XHR, since fetch() can't
    report upload progress), and on success stashes
    {file_id, mime_type, file_size, filename} as JSON in the field's
    hidden input - the admin never sees or types a Drive id.

    One module, reused by every upload field in every admin form instead
    of each entity wiring its own upload handling.
*/

function initUploadWidgets(root = document) {
    registerPaperUnloadCleanup();
    root.querySelectorAll(".upload-dropzone").forEach((dropzone) => {
        if (dropzone.dataset.uploadInitialized) {
            return;
        }
        dropzone.dataset.uploadInitialized = "true";
        wireDropzone(dropzone);
    });
}

function registerPaperUnloadCleanup() {
    if (window.paperUploadCleanupRegistered) {
        return;
    }
    window.paperUploadCleanupRegistered = true;

    window.addEventListener("pagehide", () => {
        document.querySelectorAll('form[data-entity-key="papers"]').forEach((form) => {
            if (form.dataset.paperSaveSubmitted === "true") {
                return;
            }

            form.querySelectorAll("[data-upload-hidden]").forEach((hiddenInput) => {
                if (!hiddenInput.value) {
                    return;
                }

                let uploadData;
                try {
                    uploadData = JSON.parse(hiddenInput.value);
                } catch (error) {
                    return;
                }

                if (!uploadData.file_id) {
                    return;
                }

                const formData = new FormData();
                formData.append("file_id", uploadData.file_id);
                navigator.sendBeacon("/admin/upload/remove", formData);
            });
        });
    });

    document.querySelectorAll('form[data-entity-key="papers"]').forEach((form) => {
        form.addEventListener("submit", () => {
            form.dataset.paperSaveSubmitted = "true";
        });
    });
}

function wireDropzone(dropzone) {
    const fileInput = dropzone.querySelector(".upload-input");
    const preview = dropzone.querySelector("[data-upload-preview]");
    const progressTrack = dropzone.querySelector("[data-upload-progress]");
    const progressBar = progressTrack.querySelector(".upload-progress-bar");
    const statusEl = dropzone.querySelector("[data-upload-status]");
    const hiddenInput = dropzone.parentElement.querySelector("[data-upload-hidden]");
    const category = dropzone.dataset.uploadCategory || "";
    const form = dropzone.closest("form");

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("upload-dropzone--active");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("upload-dropzone--active");
    });

    dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("upload-dropzone--active");

        if (event.dataTransfer.files.length > 0) {
            fileInput.files = event.dataTransfer.files;
            handleFile(fileInput.files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    async function handleFile(file) {
        showLocalPreview(file);
        try {
            await validateBeforeUpload();
            uploadFile(file);
        } catch (error) {
            statusEl.textContent = `Upload failed: ${error.message}`;
            statusEl.classList.add("upload-status--error");
        }
    }

    async function validateBeforeUpload() {
        if (!form || form.dataset.entityKey !== "papers") {
            return;
        }

        const formData = new FormData();
        formData.append("subject_id", form.elements.subject_id.value);
        formData.append("title", form.elements.title.value);
        formData.append("year", form.elements.year.value);
        formData.append("duration", form.elements.duration.value);
        formData.append("status", form.elements.status.value);

        const response = await fetch("/admin/papers/validate", {
            method: "POST",
            body: formData,
            credentials: "same-origin",
        });
        const data = await response.json();

        if (!response.ok || !data.valid) {
            throw new Error(data.error || "invalid Paper details");
        }
    }

    function showLocalPreview(file) {
        if (file.type.startsWith("image/")) {
            const reader = new FileReader();
            reader.onload = () => {
                preview.innerHTML = `<img src="${reader.result}" class="upload-thumbnail" alt="${file.name}">`;
            };
            reader.readAsDataURL(file);
        } else {
            preview.innerHTML = `<p class="upload-file-chip">&#128196; ${file.name}</p>`;
        }
    }

    function uploadFile(file) {
        statusEl.textContent = "";
        statusEl.className = "upload-status";
        progressTrack.hidden = false;
        progressBar.style.width = "0%";
        hiddenInput.value = "";

        const formData = new FormData();
        formData.append("file", file);
        formData.append("category", category);
        if (form && form.dataset.entityKey === "papers") {
            formData.append("subject_id", form.elements.subject_id.value);
            formData.append("title", form.elements.title.value);
            formData.append("year", form.elements.year.value);
            formData.append("duration", form.elements.duration.value);
            formData.append("status", form.elements.status.value);
        }

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/admin/upload");

        xhr.upload.addEventListener("progress", (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressBar.style.width = `${percent}%`;
            }
        });

        xhr.addEventListener("load", () => {
            progressTrack.hidden = true;

            let data;
            try {
                data = JSON.parse(xhr.responseText);
            } catch (err) {
                statusEl.textContent = "Upload failed: unexpected server response.";
                statusEl.classList.add("upload-status--error");
                return;
            }

            if (xhr.status >= 400 || data.error) {
                statusEl.textContent = `Upload failed: ${data.error || xhr.statusText}`;
                statusEl.classList.add("upload-status--error");
                return;
            }

            hiddenInput.value = JSON.stringify(data);
            statusEl.textContent = `Uploaded: ${data.filename} (${formatBytes(data.file_size)})`;
            statusEl.classList.add("upload-status--success");
            addRemoveControl();
        });

        xhr.addEventListener("error", () => {
            progressTrack.hidden = true;
            statusEl.textContent = "Upload failed. Check your connection and try again.";
            statusEl.classList.add("upload-status--error");
        });

        xhr.send(formData);
    }

    function addRemoveControl() {
        let removeBtn = dropzone.querySelector(".upload-remove-btn");
        if (removeBtn) {
            return;
        }

        removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "upload-remove-btn";
        removeBtn.textContent = "Remove";
        removeBtn.addEventListener("click", async (event) => {
            event.stopPropagation();
            const uploadData = hiddenInput.value ? JSON.parse(hiddenInput.value) : null;
            if (uploadData && uploadData.file_id) {
                const formData = new FormData();
                formData.append("file_id", uploadData.file_id);
                await fetch("/admin/upload/remove", {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin",
                });
            }
            hiddenInput.value = "";
            fileInput.value = "";
            statusEl.textContent = "";
            statusEl.className = "upload-status";
            preview.innerHTML = `
                <p class="upload-placeholder">
                    <span class="upload-icon">&#8593;</span>
                    Drag &amp; drop a file here, or <span class="upload-browse-link">choose a file</span>
                </p>
            `;
            removeBtn.remove();
        });
        dropzone.appendChild(removeBtn);
    }
}

function formatBytes(bytes) {
    if (!bytes) {
        return "0 KB";
    }
    if (bytes < 1024 * 1024) {
        return `${Math.round(bytes / 1024)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

document.addEventListener("DOMContentLoaded", () => initUploadWidgets());
