async function loadExams() {
    const response = await fetch("/api/exams/");
    const exams = await response.json();

    const container = document.getElementById("exam-container");
    container.innerHTML = "";

    if (exams.length === 0) {
        container.innerHTML = "<p>No exams published yet.</p>";
        return;
    }

    exams.forEach((exam) => {
        const card = document.createElement("a");
        card.className = "entity-card";
        card.href = `/${exam.slug}`;
        card.innerHTML = `
            <h3>${exam.name}</h3>
            <span class="entity-card-meta">${exam.description ?? ""}</span>
        `;
        container.appendChild(card);
    });
}

loadExams();
