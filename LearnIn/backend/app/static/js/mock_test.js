import { collectAnswer, createQuestionCard } from "./components/quiz-question.js";

let timerInterval = null;
let mockTestId = null;
let questionEntries = [];

function initMockTest() {
    const container = document.getElementById("mock-test-container");
    mockTestId = container.dataset.mockTestId;

    const startButton = document.getElementById("start-mock-test");
    if (startButton) {
        startButton.addEventListener("click", () => startMockTest(container));
    }
}

async function startMockTest(container) {
    const durationMinutes = parseInt(container.dataset.durationMinutes, 10);

    const response = await fetch(`/api/mock-tests/${mockTestId}/questions`);
    questionEntries = await response.json();

    if (questionEntries.length === 0) {
        container.innerHTML = "<p>No questions have been added to this mock test yet.</p>";
        return;
    }

    container.innerHTML = "";
    container.appendChild(buildTimer(durationMinutes * 60));

    questionEntries.forEach((entry, index) => {
        container.appendChild(createQuestionCard(entry.question, index));
    });

    const submitButton = document.createElement("button");
    submitButton.className = "btn";
    submitButton.textContent = "Submit Test";
    submitButton.addEventListener("click", () => submitMockTest(container));
    container.appendChild(submitButton);
}

function buildTimer(totalSeconds) {
    const timerEl = document.createElement("div");
    timerEl.className = "quiz-timer";
    timerEl.id = "quiz-timer";
    updateTimerText(timerEl, totalSeconds);

    let remaining = totalSeconds;
    timerInterval = setInterval(() => {
        remaining -= 1;
        updateTimerText(timerEl, remaining);

        if (remaining <= 0) {
            clearInterval(timerInterval);
            submitMockTest(document.getElementById("mock-test-container"));
        }
    }, 1000);

    return timerEl;
}

function updateTimerText(el, totalSeconds) {
    const minutes = Math.max(0, Math.floor(totalSeconds / 60));
    const seconds = Math.max(0, totalSeconds % 60);
    el.textContent = `Time remaining: ${minutes}:${String(seconds).padStart(2, "0")}`;
}

function collectMockAnswers(container) {
    const answers = [];

    questionEntries.forEach((entry) => {
        const question = entry.question;
        const card = container.querySelector(`[data-question-id="${question.id}"]`);
        if (!card) {
            return;
        }

        const answer = collectAnswer(question, card);

        if (answer) {
            answers.push({ question_id: question.id, answer });
        }
    });

    return answers;
}

async function submitMockTest(container) {
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    const answers = collectMockAnswers(container);

    const response = await fetch(`/api/mock-tests/${mockTestId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
    });
    const result = await response.json();

    renderResult(container, result);
}

function renderResult(container, result) {
    container.innerHTML = "";

    const summary = document.createElement("div");
    summary.className = "quiz-result-summary";
    summary.innerHTML = `
        <div class="quiz-result-stat"><span>${result.scored_marks}</span><label>Score / ${result.total_marks}</label></div>
        <div class="quiz-result-stat"><span>${result.correct_count}</span><label>Correct</label></div>
        <div class="quiz-result-stat"><span>${result.incorrect_count}</span><label>Incorrect</label></div>
        <div class="quiz-result-stat"><span>${result.unanswered_count}</span><label>Unanswered</label></div>
    `;
    container.appendChild(summary);

    const reviewHeading = document.createElement("h2");
    reviewHeading.textContent = "Review Answers";
    container.appendChild(reviewHeading);

    result.results.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "quiz-question";

        const status = item.is_correct === null ? "Unanswered" : (item.is_correct ? "Correct" : "Incorrect");
        const feedbackClass = item.is_correct ? "correct" : "incorrect";

        card.innerHTML = `
            <div class="quiz-question-header"><span>Q${index + 1}</span><span>${item.marks_awarded} marks</span></div>
            <div class="quiz-feedback ${item.is_correct === null ? "" : feedbackClass}">
                ${status} - Correct answer: ${item.correct_answer}
                ${item.explanation ? " — " + item.explanation : ""}
            </div>
        `;
        container.appendChild(card);
    });
}

initMockTest();
