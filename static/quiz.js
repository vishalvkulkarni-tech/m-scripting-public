let questions = [];
let currentQuestion = 0;
let answers = {};
let timeLeft = 30 * 60; // Will be set from server config
let timerInterval;
let startTime;
let quizSubmitted = false;

// Detect page refresh/reload and prevent cheating
window.addEventListener('beforeunload', function(e) {
    if (!quizSubmitted && questions.length > 0) {
        // Warn user before leaving during active quiz
        e.preventDefault();
        e.returnValue = 'Your quiz is in progress. If you leave, you will need to login again.';
    }
});

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
        
        // Set timer from server configuration
        if (data.quiz_time_minutes) {
            timeLeft = data.quiz_time_minutes * 60;
        }
        
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
    
    // Use radio for single answer, checkbox for multiple answers
    const inputType = q.is_multiple ? 'checkbox' : 'radio';
    
    // Process question text for Mermaid diagrams
    const processedQuestion = processDiagrams(q.question);
    
    let optionsHTML = '';
    q.options.forEach(opt => {
        // Escape single quotes in option text for JS
        const escapedText = opt.text.replace(/'/g, "\\'");
        optionsHTML += `
            <label class="option">
                <input type="${inputType}" name="q${q.id}" value="${escapedText}" 
                       onchange="handleAnswerChange(${q.id}, '${escapedText}', this.checked, '${inputType}')">
                <span>${opt.text}</span>
            </label>
        `;
    });
    
    const answerTypeHint = q.is_multiple ? 
        '<p class="answer-hint">⚠️ Multiple answers possible - select all that apply</p>' : 
        '<p class="answer-hint">ℹ️ Single answer - select one option</p>';
    
    div.innerHTML = `
        <h2>Question ${index + 1} of ${questions.length}</h2>
        <div class="question-text">${processedQuestion}</div>
        ${answerTypeHint}
        <div class="options">
            ${optionsHTML}
        </div>
    `;
    
    // Render Mermaid diagrams after DOM insertion
    setTimeout(() => {
        mermaid.run({
            nodes: div.querySelectorAll('.mermaid')
        });
    }, 100);
    
    return div;
}

function processDiagrams(text) {
    // Convert [DIAGRAM]...[/DIAGRAM] to Mermaid syntax
    const diagramRegex = /\[DIAGRAM\]([\s\S]*?)\[\/DIAGRAM\]/g;
    return text.replace(diagramRegex, (match, diagramCode) => {
        const trimmedCode = diagramCode.trim();
        return `<div class="diagram-container"><pre class="mermaid">${trimmedCode}</pre></div>`;
    });
}

function handleAnswerChange(questionId, optionText, checked, inputType) {
    if (inputType === 'radio') {
        // For radio buttons, replace the answer with the selected option
        answers[questionId] = [optionText];
    } else {
        // For checkboxes, maintain array of selected options
        if (!answers[questionId]) {
            answers[questionId] = [];
        }
        
        if (checked) {
            if (!answers[questionId].includes(optionText)) {
                answers[questionId].push(optionText);
            }
        } else {
            answers[questionId] = answers[questionId].filter(a => a !== optionText);
        }
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
    quizSubmitted = true;  // Mark quiz as submitted to prevent beforeunload warning
    
    // Send answers as arrays of option texts
    const formattedAnswers = {};
    for (const [qId, selectedOptions] of Object.entries(answers)) {
        formattedAnswers[qId] = selectedOptions; // Keep as array
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
        
        if (response.status === 401) {
            // Session expired, redirect to login
            alert('Your session has expired. Please login again.');
            window.location.href = '/logout';
            return;
        }
        
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
    
    // Overall score summary
    let resultsHTML = `
        <div class="score-summary">
            <h3>Overall Score</h3>
            <p class="main-score">${data.score} / ${data.total} (${data.percentage}%)</p>
        </div>
    `;
    
    // Subsection-wise scores
    if (data.section_wise_scores && Object.keys(data.section_wise_scores).length > 0) {
        resultsHTML += `
            <div class="subsection-scores">
                <h3>Subsection Performance</h3>
                <div class="subsection-grid">
        `;
        
        for (const [section, scores] of Object.entries(data.section_wise_scores)) {
            const percentage = scores.percentage || 0;
            const statusClass = percentage >= 70 ? 'good' : percentage >= 50 ? 'average' : 'poor';
            resultsHTML += `
                <div class="subsection-item ${statusClass}">
                    <div class="subsection-name">${section}</div>
                    <div class="subsection-score">${scores.correct} / ${scores.total}</div>
                    <div class="subsection-percentage">${percentage}%</div>
                </div>
            `;
        }
        
        resultsHTML += `
                </div>
            </div>
        `;
    }
    
    resultsHTML += `<h3>Detailed Question Review:</h3>`;
    
    data.results.forEach((result, index) => {
        const isCorrect = result.is_correct;
        const className = isCorrect ? 'correct' : 'incorrect';
        
        let optionsHTML = '';
        result.options.forEach(opt => {
            const correctTexts = result.correct_answers || [];
            const userTexts = result.user_answers || [];
            
            let optClass = '';
            if (correctTexts.includes(opt.text)) {
                optClass = 'correct-answer';
            }
            if (userTexts.includes(opt.text)) {
                optClass += ' user-answer';
            }
            
            optionsHTML += `<p class="${optClass}">${opt.text}</p>`;
        });
        
        const correctAnswerText = result.correct_answers ? result.correct_answers.join(', ') : '';
        const userAnswerText = result.user_answers && result.user_answers.length > 0 ? 
            result.user_answers.join(', ') : 'Not answered';
        
        resultsHTML += `
            <div class="result-item ${className}">
                <h4>Question ${index + 1}: ${isCorrect ? '✓ Correct' : '✗ Incorrect'}</h4>
                <p><strong>${result.question}</strong></p>
                ${optionsHTML}
                <p class="correct-answer">Correct Answer: ${correctAnswerText}</p>
                ${!isCorrect ? 
                    `<p class="user-answer">Your Answer: ${userAnswerText}</p>` : ''}
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
