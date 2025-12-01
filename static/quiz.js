let questions = [];
let currentQuestion = 0;
let answers = {};
let timeLeft = 30 * 60; // 30 minutes in seconds
let timerInterval;
let startTime;

// Load questions when page loads
document.addEventListener('DOMContentLoaded', async () => {
    await loadQuestions();
    startTimer();
    displayQuestion();
    setupEventListeners();
});

async function loadQuestions() {
    try {
        const response = await fetch('/api/questions');
        const data = await response.json();
        questions = data.questions;
        
        // Render all questions
        const container = document.getElementById('quizContainer');
        container.innerHTML = '';
        
        questions.forEach((q, index) => {
            const questionDiv = createQuestionElement(q, index);
            container.appendChild(questionDiv);
        });
        
        document.getElementById('quizFooter').style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading questions:', error);
        document.getElementById('quizContainer').innerHTML = 
            '<div class="error-message">Failed to load questions. Please refresh the page.</div>';
    }
}

function createQuestionElement(q, index) {
    const div = document.createElement('div');
    div.className = 'question';
    div.id = `question-${index}`;
    
    // Determine if multiple answers are possible (simple heuristic)
    const inputType = 'checkbox'; // Allow multiple selections for all questions
    
    let optionsHTML = '';
    q.options.forEach(opt => {
        optionsHTML += `
            <label class="option">
                <input type="${inputType}" name="q${q.id}" value="${opt.num}" 
                       onchange="handleAnswerChange(${q.id}, '${opt.num}', this.checked)">
                <span>${opt.num}. ${opt.text}</span>
            </label>
        `;
    });
    
    div.innerHTML = `
        <h2>Question ${index + 1} of ${questions.length}</h2>
        <p>${q.question}</p>
        <div class="options">
            ${optionsHTML}
        </div>
    `;
    
    return div;
}

function handleAnswerChange(questionId, optionNum, checked) {
    if (!answers[questionId]) {
        answers[questionId] = [];
    }
    
    if (checked) {
        if (!answers[questionId].includes(optionNum)) {
            answers[questionId].push(optionNum);
        }
    } else {
        answers[questionId] = answers[questionId].filter(a => a !== optionNum);
    }
    
    // Update visual feedback
    updateOptionStyles();
}

function updateOptionStyles() {
    document.querySelectorAll('.option').forEach(opt => {
        const input = opt.querySelector('input');
        if (input.checked) {
            opt.classList.add('selected');
        } else {
            opt.classList.remove('selected');
        }
    });
}

function displayQuestion() {
    // Hide all questions
    document.querySelectorAll('.question').forEach(q => {
        q.classList.remove('active');
    });
    
    // Show current question
    const currentQ = document.getElementById(`question-${currentQuestion}`);
    if (currentQ) {
        currentQ.classList.add('active');
    }
    
    // Update counter
    document.getElementById('questionCounter').textContent = 
        `Question ${currentQuestion + 1} of ${questions.length}`;
    
    // Update button states
    document.getElementById('prevBtn').disabled = currentQuestion === 0;
    document.getElementById('nextBtn').disabled = currentQuestion === questions.length - 1;
}

function setupEventListeners() {
    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentQuestion > 0) {
            currentQuestion--;
            displayQuestion();
        }
    });
    
    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentQuestion < questions.length - 1) {
            currentQuestion++;
            displayQuestion();
        }
    });
    
    document.getElementById('submitBtn').addEventListener('click', () => {
        if (confirm('Are you sure you want to submit your quiz?')) {
            submitQuiz();
        }
    });
}

function startTimer() {
    startTime = Date.now();
    const timerElement = document.getElementById('timer');
    
    timerInterval = setInterval(() => {
        timeLeft--;
        
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        
        timerElement.textContent = 
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // Warning when 5 minutes left
        if (timeLeft <= 300) {
            timerElement.classList.add('warning');
        }
        
        // Auto-submit when time's up
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            alert('Time is up! Submitting your quiz...');
            submitQuiz();
        }
    }, 1000);
}

function getTimeTaken() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

async function submitQuiz() {
    clearInterval(timerInterval);
    
    // Convert answers object to format expected by backend
    const formattedAnswers = {};
    for (const [qId, selectedOptions] of Object.entries(answers)) {
        formattedAnswers[qId] = selectedOptions.sort().join(' ');
    }
    
    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                answers: formattedAnswers,
                time_taken: getTimeTaken()
            })
        });
        
        const data = await response.json();
        displayResults(data);
        
    } catch (error) {
        console.error('Error submitting quiz:', error);
        alert('Failed to submit quiz. Please try again.');
    }
}

function displayResults(data) {
    const modal = document.getElementById('resultsModal');
    const content = document.getElementById('resultsContent');
    
    let resultsHTML = `
        <div class="score-summary">
            <h3>${data.score} / ${data.total}</h3>
            <p>Score: ${data.percentage}%</p>
        </div>
        <h3>Detailed Results:</h3>
    `;
    
    data.results.forEach((result, index) => {
        const isCorrect = result.is_correct;
        const className = isCorrect ? 'correct' : 'incorrect';
        
        let optionsHTML = '';
        result.options.forEach(opt => {
            const correctNums = result.correct_answer.split(' ');
            const userNums = result.user_answer.split(' ');
            
            let optClass = '';
            if (correctNums.includes(opt.num)) {
                optClass = 'correct-answer';
            }
            if (userNums.includes(opt.num)) {
                optClass += ' user-answer';
            }
            
            optionsHTML += `<p class="${optClass}">${opt.num}. ${opt.text}</p>`;
        });
        
        resultsHTML += `
            <div class="result-item ${className}">
                <h4>Question ${index + 1}: ${isCorrect ? '✓ Correct' : '✗ Incorrect'}</h4>
                <p><strong>${result.question}</strong></p>
                ${optionsHTML}
                <p class="correct-answer">Correct Answer: ${result.correct_answer}</p>
                ${!isCorrect && result.user_answer ? 
                    `<p class="user-answer">Your Answer: ${result.user_answer || 'Not answered'}</p>` : ''}
            </div>
        `;
    });
    
    content.innerHTML = resultsHTML;
    modal.style.display = 'flex';
}

// Keep-alive ping to prevent server sleep
setInterval(() => {
    fetch('/health').catch(() => {});
}, 14 * 60 * 1000); // Every 14 minutes
