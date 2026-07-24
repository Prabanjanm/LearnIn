/*
    Shared question-card rendering, reused by both practice.js (instant
    per-question checking) and mock_test.js (deferred, graded on submit).
    Exported as an ES module so both callers import the same DOM-building
    logic instead of maintaining two copies of it.
*/

export function createQuestionCard(question, index) {
    const card = document.createElement("div");
    card.className = "quiz-question";
    card.dataset.questionId = question.id;

    const header = document.createElement("div");
    header.className = "quiz-question-header";
    header.innerHTML = `<span>Q${index + 1}</span><span>${question.marks} marks / -${question.negative_marks}</span>`;
    card.appendChild(header);

    const text = document.createElement("p");
    text.textContent = question.question_text;
    card.appendChild(text);

    card.appendChild(createOptionsElement(question));

    return card;
}

function createOptionsElement(question) {
    const optionsWrap = document.createElement("div");
    optionsWrap.className = "quiz-options";

    if (question.question_type === "NAT") {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "quiz-nat-input";
        input.placeholder = "Enter numeric answer";
        optionsWrap.appendChild(input);
        return optionsWrap;
    }

    const inputType = question.question_type === "MSQ" ? "checkbox" : "radio";

    question.options.forEach((option) => {
        const label = document.createElement("label");
        label.className = "quiz-option";
        label.dataset.label = option.label;

        const input = document.createElement("input");
        input.type = inputType;
        input.name = `question-${question.id}`;
        input.value = option.label;

        label.appendChild(input);
        label.appendChild(document.createTextNode(`${option.label}. ${option.option_text}`));
        optionsWrap.appendChild(label);
    });

    return optionsWrap;
}

export function collectAnswer(question, card) {
    if (question.question_type === "NAT") {
        return card.querySelector(".quiz-nat-input").value.trim();
    }

    const selected = Array.from(
        card.querySelectorAll(`input[name="question-${question.id}"]:checked`)
    ).map((input) => input.value);

    return selected.join(",");
}

export function disableCardInputs(card) {
    card.querySelectorAll(".quiz-options input").forEach((input) => {
        input.disabled = true;
    });
}
