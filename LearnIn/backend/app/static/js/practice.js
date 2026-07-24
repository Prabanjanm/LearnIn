import { collectAnswer, createQuestionCard } from "./components/quiz-question.js";

async function loadPracticeQuestions() {
    const container = document.getElementById("practice-container");
    const paperId = container.dataset.paperId;

    const response = await fetch(`/api/questions/?paper_id=${paperId}`);
    const questions = await response.json();

    if (questions.length === 0) {
        container.innerHTML = "<p>No questions have been added for this paper yet.</p>";
        return;
    }

    container.innerHTML = "";

    questions.forEach((question, index) => {
        container.appendChild(renderPracticeQuestion(question, index));
    });
}

function renderPracticeQuestion(question, index) {
    const card = createQuestionCard(question, index);

    const checkButton = document.createElement("button");
    checkButton.className = "btn";
    checkButton.textContent = "Check Answer";
    checkButton.addEventListener("click", () => checkAnswer(question, card, checkButton));
    card.appendChild(checkButton);

    const feedbackSlot = document.createElement("div");
    feedbackSlot.className = "quiz-feedback-slot";
    card.appendChild(feedbackSlot);

    return card;
}

async function checkAnswer(question, card, checkButton) {
    const answer = collectAnswer(question, card);

    if (!answer) {
        return;
    }

    const response = await fetch(`/api/questions/${question.id}/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
    });
    const result = await response.json();

    const correctLabels = result.correct_answer.split(",").map((label) => label.trim().toUpperCase());

    card.querySelectorAll(".quiz-option").forEach((optionEl) => {
        const input = optionEl.querySelector("input");
        if (correctLabels.includes(optionEl.dataset.label)) {
            optionEl.classList.add("correct");
        } else if (input.checked) {
            optionEl.classList.add("incorrect");
        }
        input.disabled = true;
    });

    const natInput = card.querySelector(".quiz-nat-input");
    if (natInput) {
        natInput.disabled = true;
    }

    const feedbackSlot = card.querySelector(".quiz-feedback-slot");
    const feedback = document.createElement("div");
    feedback.className = `quiz-feedback ${result.is_correct ? "correct" : "incorrect"}`;
    feedback.textContent = result.is_correct
        ? "Correct!"
        : `Incorrect. Correct answer: ${result.correct_answer}`;

    if (result.explanation) {
        feedback.textContent += ` — ${result.explanation}`;
    }

    feedbackSlot.appendChild(feedback);
    checkButton.disabled = true;
}

loadPracticeQuestions();
