/*
    Question Paper Processing - status polling and the review screen.

    Two small, independent behaviours, both plain fetch() against the JSON
    endpoints under /api/admin/paper-processing/. No framework, no polling
    infrastructure: a setInterval is the right size of tool for "tell me
    when the in-process pipeline finished".
*/

const PP_API = "/api/admin/paper-processing";

const PP_BUSY_STATUSES = [
    "UPLOADED",
    "VALIDATING",
    "CLEANING_WATERMARK",
    "ANALYZING",
    "EXTRACTING",
    "DETECTING_QUESTIONS",
];

const PP_STATUS_LABELS = {
    UPLOADED: "Uploaded - waiting to start",
    VALIDATING: "Validating the PDF",
    VALIDATION_FAILED: "Validation failed",
    CLEANING_WATERMARK: "Checking for watermarks",
    WATERMARK_NEEDS_REVIEW: "Watermark needs manual review",
    ANALYZING: "Detecting PDF type",
    EXTRACTING: "Extracting text",
    DETECTING_QUESTIONS: "Detecting questions and options",
    READY_FOR_REVIEW: "Ready for review",
    REVIEWED: "Review saved",
    GENERATING_PDF: "Generating the LearnIn PDF",
    READY_TO_PUBLISH: "Ready to publish",
    PUBLISHED: "Published",
    FAILED: "Failed",
};

const PP_PDF_TYPE_LABELS = {
    TEXT: "Text-based",
    SCANNED: "Scanned - OCR Required",
    UNKNOWN: "Unknown",
};

async function ppRequest(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...options,
    });

    if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
            const body = await response.json();
            if (body && body.detail) {
                detail = typeof body.detail === "string" ? body.detail : detail;
            }
        } catch (err) {
            /* non-JSON error body - keep the generic message */
        }
        throw new Error(detail);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

/* ------------------------------------------------------ status polling -- */

function initStatusPolling() {
    const panel = document.querySelector("[data-pp-status]");
    if (!panel) {
        return;
    }

    const jobId = panel.dataset.jobId;
    const reviewUrl = panel.dataset.reviewUrl;
    const label = panel.querySelector("[data-pp-status-label]");
    const spinner = panel.querySelector("[data-pp-spinner]");

    // The server only renders the spinner while the pipeline is still
    // running, so its presence is the signal that there is anything to poll
    // for. A terminal state needs no polling at all.
    if (!label || !spinner) {
        return;
    }

    const timer = setInterval(async () => {
        let data;
        try {
            data = await ppRequest(`${PP_API}/${jobId}/status`);
        } catch (err) {
            // A transient failure should not kill the poll loop; a repeated
            // one just means the admin refreshes.
            return;
        }

        label.textContent = PP_STATUS_LABELS[data.status] || data.status;
        label.className = `pp-status pp-status--${String(data.status).toLowerCase()}`;

        setText(panel, "[data-pp-pdf-type]", PP_PDF_TYPE_LABELS[data.pdf_type] || "Not analysed yet");
        setText(panel, "[data-pp-ocr]", data.ocr_used ? "Yes" : "No");
        setText(panel, "[data-pp-count]", data.questions_extracted);
        setText(panel, "[data-pp-low]", data.questions_low_confidence);

        if (!PP_BUSY_STATUSES.includes(data.status)) {
            clearInterval(timer);
            if (spinner) {
                spinner.remove();
            }
            if (data.status === "READY_FOR_REVIEW" && reviewUrl) {
                window.location.href = reviewUrl;
            } else {
                window.location.reload();
            }
        }
    }, 4000);
}

function setText(root, selector, value) {
    const element = root.querySelector(selector);
    if (element) {
        element.textContent = value;
    }
}

/* --------------------------------------------------------- review screen -- */

function readQuestion(card) {
    const options = [];

    card.querySelectorAll("[data-pp-option]").forEach((input) => {
        const text = input.value.trim();
        if (text) {
            options.push({ label: input.dataset.ppOption, option_text: text });
        }
    });

    const answerInput = card.querySelector("[data-pp-answer]");
    const flag = card.querySelector("[data-pp-needs-review]");

    return {
        question_text: card.querySelector("[data-pp-text]").value.trim(),
        correct_answer: answerInput && answerInput.value.trim() ? answerInput.value.trim() : null,
        needs_review: flag ? flag.checked : null,
        options,
    };
}

/* Uploads one file through the existing /admin/upload endpoint (the same
   path every other admin upload widget uses) and returns the
   {file_id, mime_type, file_size, filename} JSON it produces. */
async function ppUploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", "question_images");

    const response = await fetch("/admin/upload", { method: "POST", body: formData, credentials: "same-origin" });
    const data = await response.json();

    if (!response.ok || data.error) {
        throw new Error(data.error || "Upload failed.");
    }

    return data;
}

function ppReportStatus(card, message, isError) {
    const status = card.querySelector("[data-pp-question-status]");
    if (!status) {
        return;
    }
    status.textContent = message;
    status.className = `pp-inline-status ${isError ? "pp-inline-status--error" : "pp-inline-status--ok"}`;
}

/* Saves the whole question card (text, options, answer) - every field
   auto-saves on blur/change now, so there is no separate per-question
   "did you remember to click Save" step. */
async function ppSaveQuestion(jobId, card) {
    const questionId = card.dataset.questionId;
    const payload = readQuestion(card);

    if (!payload.question_text) {
        ppReportStatus(card, "Question text cannot be empty.", true);
        return false;
    }

    try {
        await ppRequest(`${PP_API}/${jobId}/questions/${questionId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
        });
        ppReportStatus(card, "Saved.", false);
        return true;
    } catch (err) {
        ppReportStatus(card, err.message, true);
        return false;
    }
}

function initReview() {
    const review = document.querySelector("[data-pp-review]");
    if (!review) {
        return;
    }

    const jobId = review.dataset.jobId;

    review.querySelectorAll("[data-pp-answer]").forEach((select) => {
        select.dataset.ppPreviousValue = select.value;
    });

    review.addEventListener("click", async (event) => {
        const card = event.target.closest("[data-pp-question]");
        if (!card) {
            return;
        }

        const questionId = card.dataset.questionId;
        const status = card.querySelector("[data-pp-question-status]");

        const report = (message, isError) => {
            if (!status) {
                return;
            }
            status.textContent = message;
            status.className = `pp-inline-status ${isError ? "pp-inline-status--error" : "pp-inline-status--ok"}`;
        };

        try {
            if (event.target.matches("[data-pp-save]")) {
                await ppSaveQuestion(jobId, card);
                return;
            }

            if (event.target.matches("[data-pp-delete]")) {
                if (!window.confirm("Delete this question? This cannot be undone.")) {
                    return;
                }
                await ppRequest(`${PP_API}/${jobId}/questions/${questionId}`, { method: "DELETE" });
                card.remove();
                return;
            }

            if (event.target.matches("[data-pp-move]")) {
                await ppRequest(`${PP_API}/${jobId}/questions/${questionId}/move`, {
                    method: "POST",
                    body: JSON.stringify({ direction: event.target.dataset.ppMove }),
                });
                window.location.reload();
                return;
            }

            if (event.target.matches("[data-pp-split]")) {
                if (!window.confirm(
                    "Split this into two blocks? Both halves start from the same extracted "
                    + "text - LearnIn will not guess where the split belongs, so you edit "
                    + "each half by hand."
                )) {
                    return;
                }
                await ppRequest(`${PP_API}/${jobId}/questions/${questionId}/split`, {
                    method: "POST",
                    body: JSON.stringify({ split_at: null }),
                });
                window.location.reload();
                return;
            }

            if (event.target.matches("[data-pp-merge]")) {
                if (!window.confirm("Merge this question with the next one into a single editable block?")) {
                    return;
                }
                await ppRequest(`${PP_API}/${jobId}/questions/${questionId}/merge`, { method: "POST" });
                window.location.reload();
                return;
            }

            const imageItem = event.target.closest("[data-pp-image]");

            if (event.target.matches("[data-pp-image-remove]")) {
                if (!window.confirm("Remove this image from the question? This cannot be undone.")) {
                    return;
                }
                await ppRequest(
                    `${PP_API}/${jobId}/questions/${questionId}/images/${imageItem.dataset.imageId}`,
                    { method: "DELETE" },
                );
                window.location.reload();
                return;
            }

            if (event.target.matches("[data-pp-image-move]")) {
                await ppRequest(
                    `${PP_API}/${jobId}/questions/${questionId}/images/${imageItem.dataset.imageId}/move`,
                    { method: "POST", body: JSON.stringify({ direction: event.target.dataset.ppImageMove }) },
                );
                window.location.reload();
                return;
            }

            if (event.target.matches("[data-pp-image-reassign]")) {
                const target = window.prompt("Move this image to which question number? (enter the Q number shown above each question)");
                if (!target || !target.trim()) {
                    return;
                }
                const targetQuestion = Array.from(review.querySelectorAll("[data-pp-question]")).find(
                    (candidate) => candidate.querySelector(".pp-question-index").textContent.trim() === `Q${target.trim()}`
                );
                if (!targetQuestion) {
                    window.alert("No question with that number was found on this page.");
                    return;
                }
                await ppRequest(
                    `${PP_API}/${jobId}/questions/${questionId}/images/${imageItem.dataset.imageId}/reassign`,
                    { method: "POST", body: JSON.stringify({ target_question_id: targetQuestion.dataset.questionId }) },
                );
                window.location.reload();
                return;
            }
        } catch (err) {
            report(err.message, true);
        }
    });

    review.addEventListener("change", async (event) => {
        if (event.target.matches("[data-pp-answer]")) {
            const card = event.target.closest("[data-pp-question]");
            const previousValue = event.target.dataset.ppPreviousValue || "";

            const saved = await ppSaveQuestion(jobId, card);
            event.target.dataset.ppPreviousValue = saved ? event.target.value : previousValue;
            if (!saved) {
                event.target.value = previousValue;
            }
            return;
        }

        if (event.target.matches("[data-pp-text], [data-pp-option]")) {
            const card = event.target.closest("[data-pp-question]");
            await ppSaveQuestion(jobId, card);
            return;
        }

        if (event.target.matches("[data-pp-needs-review]")) {
            const card = event.target.closest("[data-pp-question]");
            const questionId = card.dataset.questionId;

            try {
                await ppRequest(`${PP_API}/${jobId}/questions/${questionId}/needs-review`, {
                    method: "POST",
                    body: JSON.stringify({ needs_review: event.target.checked }),
                });
                card.classList.toggle("pp-question--flagged", event.target.checked);
            } catch (err) {
                event.target.checked = !event.target.checked;
            }
            return;
        }

        if (event.target.matches("[data-pp-image-add], [data-pp-image-replace]")) {
            const file = event.target.files[0];
            if (!file) {
                return;
            }

            const card = event.target.closest("[data-pp-question]");
            const questionId = card.dataset.questionId;
            const imageItem = event.target.closest("[data-pp-image]");

            try {
                const uploaded = await ppUploadImage(file);

                if (event.target.matches("[data-pp-image-replace]")) {
                    await ppRequest(
                        `${PP_API}/${jobId}/questions/${questionId}/images/${imageItem.dataset.imageId}`,
                        { method: "PUT", body: JSON.stringify(uploaded) },
                    );
                } else {
                    await ppRequest(`${PP_API}/${jobId}/questions/${questionId}/images`, {
                        method: "POST",
                        body: JSON.stringify(uploaded),
                    });
                }
                window.location.reload();
            } catch (err) {
                window.alert(err.message);
            }
        }
    });

    const addButton = document.querySelector("[data-pp-add]");
    if (addButton) {
        addButton.addEventListener("click", async () => {
            const text = window.prompt("Question text (type it exactly as it appears in the paper):");
            if (!text || !text.trim()) {
                return;
            }
            try {
                await ppRequest(`${PP_API}/${addButton.dataset.jobId}/questions`, {
                    method: "POST",
                    body: JSON.stringify({ question_text: text.trim(), options: [] }),
                });
                window.location.reload();
            } catch (err) {
                window.alert(err.message);
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initStatusPolling();
    initReview();
});
