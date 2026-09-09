import { collectAnswer, createOptionsElementForResume } from "./components/quiz-question.js";

let timerInterval = null;
let mockTestId = null;
let questionEntries = [];
let clientToken = null;
let deadlineMs = null; // authoritative - derived from the server's remaining_seconds on every /start call
let currentIndex = 0;
let answers = {}; // question_id -> answer string (server-confirmed, overlaid with any pending local edits)
let marked = new Set(); // question_id set
let pending = {}; // question_id -> {answer, marked} not yet confirmed saved by the server
let retryInterval = null;

/*
    Server-side answer persistence: the server (MockTestSession +
    MockTestSessionAnswer, see mock_test_attempt/service.py) is the
    authoritative record of what a student answered/marked during an
    active test - not localStorage. Every Save & Next / Mark for Review /
    Clear Answer calls POST /api/mock-tests/{id}/answer immediately.
    localStorage here is *only* a retry queue for edits the server hasn't
    confirmed yet (a save that failed, or is still in flight) - on the
    next load/refresh, the server's own answers/marked (from /start) are
    the base state, and only genuinely unconfirmed local edits are
    reapplied on top and retried. A confirmed server answer is never
    overwritten by stale local data.
*/

function storageKey(id) {
    return `learnin_mock_test_pending_${id}`;
}

function generateClientToken() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function loadClientToken(id) {
    try {
        const raw = window.localStorage.getItem(storageKey(id));
        if (!raw) return null;
        return JSON.parse(raw).clientToken || null;
    } catch (err) {
        return null;
    }
}

function loadPending(id) {
    try {
        const raw = window.localStorage.getItem(storageKey(id));
        if (!raw) return {};
        return JSON.parse(raw).pending || {};
    } catch (err) {
        return {};
    }
}

function persistPending() {
    try {
        window.localStorage.setItem(storageKey(mockTestId), JSON.stringify({ clientToken, pending }));
    } catch (err) {
        // localStorage can throw in private-browsing/quota-exceeded cases -
        // saves still go straight to the server, they just won't have a
        // local retry queue if one fails.
    }
}

function setSaveStatus(text, isError) {
    const el = document.getElementById("cbt-save-status");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("cbt-save-status--error", Boolean(isError));
    el.classList.toggle("cbt-save-status--saved", !isError && text === "Saved");
}

function initMockTest() {
    const container = document.getElementById("mock-test-container");
    mockTestId = container.dataset.mockTestId;

    const startButton = document.getElementById("start-mock-test");
    if (startButton) {
        startButton.addEventListener("click", () => startMockTest(container));
    }
}

async function startMockTest(container) {
    clientToken = loadClientToken(mockTestId) || generateClientToken();
    pending = loadPending(mockTestId);

    const startResponse = await fetch(`/api/mock-tests/${mockTestId}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_token: clientToken }),
    });

    if (!startResponse.ok) {
        container.innerHTML = "<p>Couldn't start this test right now. Please try again.</p>";
        return;
    }

    const startState = await startResponse.json();

    if (startState.submitted) {
        // Already submitted under this client_token (e.g. reopened after
        // closing the browser post-submit) - go straight to the result
        // rather than re-showing a test that's already finalized.
        window.localStorage.removeItem(storageKey(mockTestId));
        window.location.href = `${window.location.pathname}/result/${startState.attempt_id}`;
        return;
    }

    deadlineMs = Date.now() + startState.remaining_seconds * 1000;

    if (startState.remaining_seconds <= 0) {
        submitMockTest(container, true);
        return;
    }

    // Server state is the base; only unconfirmed local edits overlay it.
    answers = { ...startState.answers };
    marked = new Set(startState.marked);
    Object.entries(pending).forEach(([questionId, entry]) => {
        if (entry.answer) {
            answers[questionId] = entry.answer;
        } else {
            delete answers[questionId];
        }
        if (entry.marked) {
            marked.add(parseInt(questionId, 10));
        } else {
            marked.delete(parseInt(questionId, 10));
        }
    });

    const response = await fetch(`/api/mock-tests/${mockTestId}/questions`);
    questionEntries = await response.json();

    if (questionEntries.length === 0) {
        container.innerHTML = "<p>No questions have been added to this mock test yet.</p>";
        return;
    }

    document.body.classList.add("test-in-progress");
    renderTestScreen(container);
    flushPending();
    retryInterval = setInterval(flushPending, 5000);
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
                <span><span class="cbt-legend-swatch cbt-legend-swatch--marked"></span> Marked for review</span>
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
            // A UX trigger only - the server independently re-checks
            // MockTestSession.started_at against the mock test's duration
            // on every /answer and /submit call, so even if this client
            // tick never fires, the server-side deadline still holds.
            submitMockTest(document.getElementById("mock-test-container"), true);
        }
    }

    tick();
    timerInterval = setInterval(tick, 1000);
}

async function saveAnswerToServer(questionId, answer, isMarked) {
    try {
        const response = await fetch(`/api/mock-tests/${mockTestId}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                client_token: clientToken,
                question_id: questionId,
                answer: answer || "",
                marked: isMarked,
            }),
        });
        return response.ok;
    } catch (err) {
        return false;
    }
}

async function persistAnswer(questionId) {
    const answer = answers[questionId] || "";
    const isMarked = marked.has(questionId);

    pending[questionId] = { answer, marked: isMarked };
    persistPending();
    setSaveStatus("Saving...");

    const ok = await saveAnswerToServer(questionId, answer, isMarked);

    if (ok) {
        delete pending[questionId];
        persistPending();
        setSaveStatus("Saved");
    } else {
        setSaveStatus("Couldn't save - retrying...", true);
    }
}

async function flushPending() {
    const pendingIds = Object.keys(pending);
    if (pendingIds.length === 0) {
        return;
    }

    setSaveStatus("Retrying...", true);

    for (const questionId of pendingIds) {
        const entry = pending[questionId];
        const ok = await saveAnswerToServer(parseInt(questionId, 10), entry.answer, entry.marked);
        if (ok) {
            delete pending[questionId];
        }
    }
    persistPending();

    setSaveStatus(Object.keys(pending).length === 0 ? "Saved" : "Couldn't save - retrying...", Object.keys(pending).length > 0);
}

function saveCurrentAnswer() {
    const card = document.getElementById("cbt-current-card");
    if (!card) return;

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

    const isLastQuestion = index === questionEntries.length - 1;

    if (isLastQuestion) {
        const notice = document.createElement("p");
        notice.className = "cbt-last-question-notice";
        notice.textContent = "You've reached the last question. Save your answer, then click “Submit Test” above when you're ready to finish.";
        panel.appendChild(notice);
    }

    const controls = document.createElement("div");
    controls.className = "cbt-controls";
    controls.innerHTML = `
        <button type="button" class="btn btn-secondary" id="cbt-prev" ${index === 0 ? "disabled" : ""}>Previous</button>
        <button type="button" class="btn btn-secondary" id="cbt-clear">Clear Answer</button>
        <button type="button" class="btn btn-secondary" id="cbt-mark">${marked.has(question.id) ? "Unmark Review" : "Mark for Review"}</button>
        <span class="spacer"></span>
        <button type="button" class="btn" id="cbt-next">${isLastQuestion ? "Save Answer" : "Save & Next"}</button>
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
    controls.querySelector("#cbt-mark").addEventListener("click", () => {
        if (marked.has(question.id)) {
            marked.delete(question.id);
        } else {
            marked.add(question.id);
        }
        saveCurrentAnswer();
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
    let markedCount = 0;

    questionEntries.forEach((entry, index) => {
        const question = entry.question;
        const isAnswered = Object.prototype.hasOwnProperty.call(answers, question.id);
        const isMarked = marked.has(question.id);
        const isCurrent = index === currentIndex;

        if (isAnswered) answeredCount += 1;
        if (isMarked) markedCount += 1;

        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(index + 1);
        button.className = "cbt-nav-q";
        if (isAnswered) button.classList.add("cbt-nav-q--answered");
        if (isMarked) button.classList.add("cbt-nav-q--marked");
        if (isCurrent) button.classList.add("cbt-nav-q--current");

        const stateLabel = [
            isAnswered ? "Answered" : "Unanswered",
            isMarked ? "Marked for review" : null,
        ].filter(Boolean).join(", ");
        button.title = `Question ${index + 1} - ${stateLabel}`;
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
        <span>Marked: ${markedCount}</span>
    `;
}

function confirmAndSubmit(container) {
    saveCurrentAnswer();

    const answeredCount = Object.keys(answers).length;
    const unansweredCount = questionEntries.length - answeredCount;
    const markedCount = marked.size;

    const overlay = document.createElement("div");
    overlay.className = "cbt-modal-overlay";
    overlay.innerHTML = `
        <div class="cbt-modal" role="dialog" aria-modal="true" aria-labelledby="cbt-modal-title">
            <h2 id="cbt-modal-title">Submit Test?</h2>
            <div class="cbt-modal-stats">
                <span>Answered <strong>${answeredCount}</strong></span>
                <span>Unanswered <strong>${unansweredCount}</strong></span>
                <span>Marked for review <strong>${markedCount}</strong></span>
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
        submitMockTest(container, false);
    });
}

let submissionInFlight = false;

async function submitMockTest(container, isAutoSubmit) {
    if (submissionInFlight) {
        return;
    }
    submissionInFlight = true;

    if (timerInterval) clearInterval(timerInterval);
    if (retryInterval) clearInterval(retryInterval);

    saveCurrentAnswer();
    await flushPending();

    container.innerHTML = `<p>${isAutoSubmit ? "Time's up - submitting your test..." : "Submitting your test..."}</p>`;

    // No answers are sent in this request - the server grades whatever
    // was persisted via /answer against this client_token's session (see
    // mock_test_service.submit_attempt), so a stale/edited in-memory
    // answers object here can't influence the result.
    const response = await fetch(`/api/mock-tests/${mockTestId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_token: clientToken }),
    });
    const result = await response.json();

    try {
        window.localStorage.removeItem(storageKey(mockTestId));
    } catch (err) {
        // ignore
    }
    document.body.classList.remove("test-in-progress");

    // The result page is a real, durable, shareable server-rendered page
    // (see mock_test/result.html) rather than something rebuilt in-memory
    // here, so a refresh or a shared link shows the same result later.
    window.location.href = `${window.location.pathname}/result/${result.attempt_id}`;
}

initMockTest();
