import { collectAnswer, createOptionsElementForResume } from "./components/quiz-question.js";

/*
    Institute-conducted test CBT engine. Deliberately simpler than
    mock_test.js in one respect: there is no client_token / localStorage
    retry queue, because a conducted test has exactly one attempt per
    logged-in student (enforced by the server's unique constraint), so
    the student's own session cookie is all that's needed to resume - a
    refresh just calls /start again and gets the same attempt back.

    What's new here that mock_test.js doesn't need: fullscreen is
    requested on this container specifically (not the whole document) -
    the browser then only displays this element, which is what actually
    satisfies "hide normal site navigation" without a separate layout.
    visibilitychange/fullscreenchange are then watched for the rest of
    the attempt; either one immediately force-submits and locks it.
*/

let conductedTestId = null;
let timerInterval = null;
let deadlineMs = null;
let questionEntries = [];
let currentIndex = 0;
let answers = {};
let violationHandled = false;
let submissionInFlight = false;

function initConductedTest() {
    const container = document.getElementById("conducted-test-container");
    if (!container) return;
    conductedTestId = container.dataset.conductedTestId;

    const acceptBox = document.getElementById("accept-rules");
    const startButton = document.getElementById("start-conducted-test");
    if (!acceptBox || !startButton) return;

    acceptBox.addEventListener("change", () => {
        startButton.disabled = !acceptBox.checked;
    });

    startButton.addEventListener("click", () => beginTest(container));
}

async function beginTest(container) {
    const errorEl = document.getElementById("start-test-error");
    errorEl.hidden = true;

    try {
        if (container.requestFullscreen) {
            await container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
            container.webkitRequestFullscreen();
        }
    } catch (err) {
        // Some browsers/embedded contexts refuse fullscreen (e.g. an
        // iframe without the allow="fullscreen" attribute) - the test
        // still proceeds server-side-timed either way; fullscreen is a
        // deterrent, not the security boundary itself.
    }

    const response = await fetch(`/api/conducted-tests/${conductedTestId}/start`, { method: "POST" });
    const data = await response.json();

    if (!response.ok) {
        errorEl.textContent = data.detail || "Could not start this test.";
        errorEl.hidden = false;
        return;
    }

    deadlineMs = Date.now() + data.remaining_seconds * 1000;
    questionEntries = data.questions;
    answers = { ...data.answers };

    if (questionEntries.length === 0) {
        container.innerHTML = "<p>No questions have been added to this test yet.</p>";
        return;
    }

    document.body.classList.add("test-in-progress");
    attachViolationWatchers();
    renderTestScreen(container);
}

function attachViolationWatchers() {
    document.addEventListener("visibilitychange", onVisibilityChange);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);
}

function detachViolationWatchers() {
    document.removeEventListener("visibilitychange", onVisibilityChange);
    document.removeEventListener("fullscreenchange", onFullscreenChange);
    document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
}

function onVisibilityChange() {
    if (document.hidden) {
        reportViolation("TAB_SWITCH");
    }
}

function onFullscreenChange() {
    const inFullscreen = Boolean(document.fullscreenElement || document.webkitFullscreenElement);
    if (!inFullscreen) {
        reportViolation("FULLSCREEN_EXIT");
    }
}

async function reportViolation(reason) {
    if (violationHandled || submissionInFlight) return;
    violationHandled = true;

    saveCurrentAnswer();
    detachViolationWatchers();
    if (timerInterval) clearInterval(timerInterval);

    const container = document.getElementById("conducted-test-container");
    if (container) {
        container.innerHTML = `<p>Test locked: ${reason === "TAB_SWITCH" ? "you switched away from this tab" : "you exited fullscreen"}. Your latest saved answers were submitted automatically.</p>`;
    }

    try {
        const response = await fetch(`/api/conducted-tests/${conductedTestId}/violation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason }),
        });
        const result = await response.json();
        document.body.classList.remove("test-in-progress");
        window.location.href = `/conducted-tests/results/${result.result_code}`;
    } catch (err) {
        // Network failure at the exact moment of violation: the server's
        // own lazy-expiry check (see service.py::start_or_resume /
        // save_answer) still finalizes this attempt the next time it's
        // touched, so the attempt can never be silently resumed either way.
    }
}

function remainingSeconds() {
    return Math.max(0, Math.round((deadlineMs - Date.now()) / 1000));
}

function renderTestScreen(container) {
    container.innerHTML = "";
    container.className = "";

    const header = document.createElement("div");
    header.className = "cbt-header";
    header.innerHTML = `
        <img class="cbt-header-logo" src="/static/img/brand/logo-mark.webp" alt="LearnIn" width="24" height="24">
        <span class="cbt-header-title">${container.dataset.title}</span>
        <span class="cbt-save-status" id="cbt-save-status"></span>
        <span class="quiz-timer" id="quiz-timer" role="timer" aria-live="polite"></span>
        <button type="button" class="btn" id="cbt-submit-btn">Submit Test</button>
    `;
    container.appendChild(header);

    const layout = document.createElement("div");
    layout.className = "cbt-layout";
    layout.innerHTML = `
        <div class="cbt-question-panel" id="cbt-question-panel"></div>
        <div class="cbt-navigator">
            <div class="cbt-navigator-legend">
                <span><span class="cbt-legend-swatch cbt-legend-swatch--current"></span> Current</span>
                <span><span class="cbt-legend-swatch cbt-legend-swatch--answered"></span> Answered</span>
                <span><span class="cbt-legend-swatch cbt-legend-swatch--unanswered"></span> Unanswered</span>
            </div>
            <div class="cbt-navigator-grid" id="cbt-navigator-grid"></div>
            <div class="cbt-navigator-summary" id="cbt-navigator-summary"></div>
        </div>
    `;
    container.appendChild(layout);

    header.querySelector("#cbt-submit-btn").addEventListener("click", () => confirmAndSubmit(container));

    startTimer();
    renderNavigator();
    renderQuestion(0);
}

function startTimer() {
    const timerEl = document.getElementById("quiz-timer");

    function tick() {
        const remaining = remainingSeconds();
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        timerEl.textContent = `Time remaining: ${minutes}:${String(seconds).padStart(2, "0")}`;
        timerEl.classList.toggle("quiz-timer--low", remaining <= 60 && remaining > 0);

        if (remaining <= 0) {
            clearInterval(timerInterval);
            // A UX trigger only - the server independently re-checks the
            // conducted test's fixed scheduled window on every /answer
            // and /submit call, so even if this client tick never fires,
            // the real deadline still holds server-side.
            submitTest(document.getElementById("conducted-test-container"));
        }
    }

    tick();
    timerInterval = setInterval(tick, 1000);
}

function setSaveStatus(text, isError) {
    const el = document.getElementById("cbt-save-status");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("cbt-save-status--error", Boolean(isError));
}

async function persistAnswer(questionId) {
    const answer = answers[questionId] || "";
    setSaveStatus("Saving...");

    try {
        const response = await fetch(`/api/conducted-tests/${conductedTestId}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question_id: questionId, answer }),
        });
        setSaveStatus(response.ok ? "Saved" : "Couldn't save", !response.ok);
    } catch (err) {
        setSaveStatus("Couldn't save", true);
    }
}

function saveCurrentAnswer() {
    const card = document.getElementById("cbt-current-card");
    if (!card || !questionEntries[currentIndex]) return;

    const question = questionEntries[currentIndex].question;
    const answer = collectAnswer(question, card);

    if (answer) {
        answers[question.id] = answer;
    } else {
        delete answers[question.id];
    }

    persistAnswer(question.id);
}

function renderQuestion(index) {
    currentIndex = index;
    const entry = questionEntries[index];
    const question = entry.question;
    const panel = document.getElementById("cbt-question-panel");

    panel.innerHTML = "";

    const meta = document.createElement("div");
    meta.className = "cbt-question-meta";
    meta.innerHTML = `<span>Question ${index + 1} of ${questionEntries.length}</span><span>${question.marks} marks / -${question.negative_marks}</span>`;
    panel.appendChild(meta);

    const text = document.createElement("p");
    text.className = "cbt-question-text";
    text.textContent = question.question_text;
    panel.appendChild(text);

    if (question.image_url) {
        const img = document.createElement("img");
        img.src = question.image_url;
        img.alt = "Question image";
        img.className = "cbt-question-image";
        panel.appendChild(img);
    }

    const card = document.createElement("div");
    card.id = "cbt-current-card";
    card.dataset.questionId = question.id;
    card.appendChild(createOptionsElementForResume(question, answers[question.id]));
    panel.appendChild(card);

    const controls = document.createElement("div");
    controls.className = "cbt-controls";
    controls.innerHTML = `
        <button type="button" class="btn-ghost" id="cbt-prev" ${index === 0 ? "disabled" : ""}>Previous</button>
        <button type="button" class="btn-ghost" id="cbt-clear">Clear Answer</button>
        <span class="spacer"></span>
        <button type="button" class="btn" id="cbt-next">${index === questionEntries.length - 1 ? "Save" : "Save & Next"}</button>
    `;
    panel.appendChild(controls);

    controls.querySelector("#cbt-prev").addEventListener("click", () => {
        saveCurrentAnswer();
        goToQuestion(index - 1);
    });
    controls.querySelector("#cbt-clear").addEventListener("click", () => {
        delete answers[question.id];
        persistAnswer(question.id);
        renderQuestion(index);
        renderNavigator();
    });
    controls.querySelector("#cbt-next").addEventListener("click", () => {
        saveCurrentAnswer();
        if (index < questionEntries.length - 1) {
            goToQuestion(index + 1);
        } else {
            renderNavigator();
        }
    });

    renderNavigator();
}

function goToQuestion(index) {
    if (index < 0 || index >= questionEntries.length) return;
    renderQuestion(index);
}

function renderNavigator() {
    const grid = document.getElementById("cbt-navigator-grid");
    grid.innerHTML = "";

    let answeredCount = 0;

    questionEntries.forEach((entry, index) => {
        const question = entry.question;
        const isAnswered = Object.prototype.hasOwnProperty.call(answers, question.id);
        const isCurrent = index === currentIndex;

        if (isAnswered) answeredCount += 1;

        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(index + 1);
        button.className = "cbt-nav-q";
        if (isAnswered) button.classList.add("cbt-nav-q--answered");
        if (isCurrent) button.classList.add("cbt-nav-q--current");

        button.title = `Question ${index + 1} - ${isAnswered ? "Answered" : "Unanswered"}`;
        button.setAttribute("aria-label", button.title);
        if (isCurrent) button.setAttribute("aria-current", "true");

        button.addEventListener("click", () => {
            saveCurrentAnswer();
            goToQuestion(index);
        });

        grid.appendChild(button);
    });

    const unansweredCount = questionEntries.length - answeredCount;
    document.getElementById("cbt-navigator-summary").innerHTML = `
        <span>Answered: ${answeredCount}</span>
        <span>Unanswered: ${unansweredCount}</span>
    `;
}

function confirmAndSubmit(container) {
    saveCurrentAnswer();

    const answeredCount = Object.keys(answers).length;
    const unansweredCount = questionEntries.length - answeredCount;

    const overlay = document.createElement("div");
    overlay.className = "cbt-modal-overlay";
    overlay.innerHTML = `
        <div class="cbt-modal" role="dialog" aria-modal="true" aria-labelledby="cbt-modal-title">
            <h2 id="cbt-modal-title">Submit Test?</h2>
            <div class="cbt-modal-stats">
                <span>Answered <strong>${answeredCount}</strong></span>
                <span>Unanswered <strong>${unansweredCount}</strong></span>
            </div>
            <div class="cbt-modal-actions">
                <button type="button" class="btn btn-secondary" id="cbt-modal-cancel">Continue Test</button>
                <button type="button" class="btn" id="cbt-modal-submit">Submit Test</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector("#cbt-modal-cancel").addEventListener("click", () => overlay.remove());
    overlay.querySelector("#cbt-modal-submit").addEventListener("click", () => {
        overlay.remove();
        submitTest(container);
    });
}

async function submitTest(container) {
    if (submissionInFlight) return;
    submissionInFlight = true;
    violationHandled = true; // stop the violation watchers from firing during our own fullscreen exit

    if (timerInterval) clearInterval(timerInterval);
    detachViolationWatchers();
    saveCurrentAnswer();

    container.innerHTML = "<p>Submitting your test...</p>";

    if (document.fullscreenElement || document.webkitFullscreenElement) {
        try {
            if (document.exitFullscreen) await document.exitFullscreen();
            else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
        } catch (err) {
            // ignore
        }
    }

    const response = await fetch(`/api/conducted-tests/${conductedTestId}/submit`, { method: "POST" });
    const result = await response.json();

    document.body.classList.remove("test-in-progress");
    window.location.href = `/conducted-tests/results/${result.result_code}`;
}

initConductedTest();
