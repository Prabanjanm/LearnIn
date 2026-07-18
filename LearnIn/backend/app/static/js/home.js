async function loadExams() {

    const response = await fetch("/api/exams/");

    const exams = await response.json();

    const container =
        document.getElementById("exam-container");

    container.innerHTML = "";

    exams.forEach(exam => {

        container.innerHTML += `

        <div
            class="exam-card"
            onclick="openExam('${exam.slug}')"
        >

            <h3>${exam.name}</h3>

            <p>${exam.description ?? ""}</p>

        </div>

        `;

    });

}

function openExam(slug){

    window.location.href=`/exam/${slug}`;

}

loadExams();