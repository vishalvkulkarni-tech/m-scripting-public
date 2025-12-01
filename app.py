import os
import json
import random
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
PRIVATE_REPO = os.environ.get('PRIVATE_REPO')  # Format: username/repo-name

# Persistent disk for results
RESULTS_DIR = os.environ.get('RESULTS_DIR', './data')
RESULTS_FILE = os.path.join(RESULTS_DIR, 'results.json')

# Create data directory if it doesn't exist
Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)

def fetch_from_github(filename):
    """Fetch file content from private GitHub repository"""
    if not GITHUB_TOKEN or not PRIVATE_REPO:
        raise Exception("GitHub credentials not configured")
    
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{filename}"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch {filename}: {response.status_code}")

def load_users():
    """Load users from private repository"""
    try:
        users_json = fetch_from_github('users.json')
        return json.loads(users_json)
    except Exception as e:
        print(f"Error loading users: {e}")
        return {"users": []}

def load_database():
    """Load question database from private repository"""
    try:
        return fetch_from_github('m_script_database.txt')
    except Exception as e:
        print(f"Error loading database: {e}")
        return ""

def parse_database(content):
    """Parse database file to extract sections and questions"""
    lines = content.split('\n')
    sections = []
    questions = []
    
    current_section = {'name': '', 'count': 0, 'question_indices': []}
    current_question = ''
    in_question = False
    
    for line in lines:
        line_stripped = line.strip()
        
        # Check for section header
        if line_stripped.startswith('SECTION:'):
            if current_section['name']:
                sections.append(current_section)
            section_name = line_stripped[8:].strip()
            current_section = {'name': section_name, 'count': 0, 'question_indices': []}
            continue
        
        # Check for question start
        if line_stripped.startswith('QUESTION '):
            if in_question and current_question:
                questions.append(current_question.strip())
                current_section['count'] += 1
                current_section['question_indices'].append(len(questions) - 1)
            current_question = line
            in_question = True
        elif in_question:
            current_question += '\n' + line
            if line_stripped.startswith('ANSWER:'):
                questions.append(current_question.strip())
                current_section['count'] += 1
                current_section['question_indices'].append(len(questions) - 1)
                current_question = ''
                in_question = False
    
    if current_section['name']:
        sections.append(current_section)
    
    return sections, questions

def parse_question(question_text):
    """Parse individual question to extract components"""
    lines = question_text.split('\n')
    question_num = ''
    question = ''
    options = []
    answer = ''
    
    in_options = False
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped.startswith('QUESTION '):
            # Extract question number and text
            match = re.match(r'QUESTION (\d+)\.\s*(.*)', line_stripped)
            if match:
                question_num = match.group(1)
                question = match.group(2)
        elif line_stripped.startswith('OPTIONS:'):
            in_options = True
        elif line_stripped.startswith('ANSWER:'):
            in_options = False
            answer = line_stripped[7:].strip()
        elif in_options and line_stripped:
            # Parse option (format: "1. option text")
            match = re.match(r'(\d+)\.\s*(.*)', line_stripped)
            if match:
                options.append({
                    'num': match.group(1),
                    'text': match.group(2)
                })
        elif not line_stripped.startswith('OPTIONS:') and not in_options and question:
            # Continue question text
            question += ' ' + line_stripped
    
    return {
        'number': question_num,
        'question': question.strip(),
        'options': options,
        'answer': answer
    }

def generate_random_questions(num_questions=30):
    """Generate random questions with 50% from Section 1"""
    database_content = load_database()
    sections, questions = parse_database(database_content)
    
    if not sections or not questions:
        return []
    
    # Allocate 50% to Section 1
    questions_from_section1 = min(round(num_questions * 0.5), sections[0]['count'])
    questions_per_section = [questions_from_section1] + [0] * (len(sections) - 1)
    
    # Distribute remaining among other sections
    remaining = num_questions - questions_from_section1
    if len(sections) > 1 and remaining > 0:
        other_counts = [s['count'] for s in sections[1:]]
        total_other = sum(other_counts)
        
        if total_other > 0:
            for i, count in enumerate(other_counts):
                weight = count / total_other
                questions_per_section[i + 1] = round(remaining * weight)
            
            # Adjust for rounding
            while sum(questions_per_section) < num_questions:
                for i in range(1, len(questions_per_section)):
                    if sum(questions_per_section) < num_questions:
                        questions_per_section[i] += 1
            
            while sum(questions_per_section) > num_questions:
                for i in range(len(questions_per_section) - 1, 0, -1):
                    if questions_per_section[i] > 0 and sum(questions_per_section) > num_questions:
                        questions_per_section[i] -= 1
    
    # Select random questions from each section
    selected = []
    for i, section in enumerate(sections):
        if questions_per_section[i] > 0:
            available = section['question_indices']
            num_to_select = min(questions_per_section[i], len(available))
            selected_indices = random.sample(available, num_to_select)
            
            for idx in selected_indices:
                selected.append(questions[idx])
    
    # Shuffle questions
    random.shuffle(selected)
    
    # Parse each question
    parsed_questions = []
    for i, q_text in enumerate(selected):
        parsed = parse_question(q_text)
        parsed['id'] = i + 1
        parsed_questions.append(parsed)
    
    return parsed_questions

def save_result(username, score, total, time_taken):
    """Save quiz result to persistent disk"""
    result = {
        'username': username,
        'score': score,
        'total': total,
        'percentage': round((score / total) * 100, 2) if total > 0 else 0,
        'time_taken': time_taken,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Load existing results
    results = []
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
        except:
            results = []
    
    # Append new result
    results.append(result)
    
    # Save back
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

@app.route('/')
def index():
    """Landing page - redirect to login or quiz"""
    if 'username' in session:
        return redirect(url_for('quiz'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # Load users
        users_data = load_users()
        users = users_data.get('users', [])
        
        # Find user
        user = next((u for u in users if u['username'] == username), None)
        
        if user:
            # Verify password (plain text comparison)
            if user['password'] == password:
                session['username'] = username
                return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.pop('username', None)
    session.pop('questions', None)
    return redirect(url_for('login'))

@app.route('/quiz')
def quiz():
    """Quiz page"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Generate new questions for this session
    questions = generate_random_questions(30)
    session['questions'] = questions
    
    return render_template('quiz.html', username=session['username'])

@app.route('/api/questions')
def get_questions():
    """API endpoint to get questions"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    questions = session.get('questions', [])
    
    # Return questions without answers
    questions_without_answers = []
    for q in questions:
        questions_without_answers.append({
            'id': q['id'],
            'question': q['question'],
            'options': q['options']
        })
    
    return jsonify({'questions': questions_without_answers})

@app.route('/api/submit', methods=['POST'])
def submit_quiz():
    """Submit quiz and get results"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_answers = data.get('answers', {})
    time_taken = data.get('time_taken', '00:00')
    
    questions = session.get('questions', [])
    
    # Calculate score
    score = 0
    results = []
    
    for q in questions:
        q_id = str(q['id'])
        correct_answer = q['answer']
        user_answer = user_answers.get(q_id, '')
        
        # Handle multiple correct answers
        correct_answers = set(correct_answer.split())
        user_answers_set = set(user_answer.split())
        
        is_correct = correct_answers == user_answers_set
        if is_correct:
            score += 1
        
        results.append({
            'id': q['id'],
            'question': q['question'],
            'options': q['options'],
            'correct_answer': correct_answer,
            'user_answer': user_answer,
            'is_correct': is_correct
        })
    
    # Save result
    save_result(session['username'], score, len(questions), time_taken)
    
    return jsonify({
        'score': score,
        'total': len(questions),
        'percentage': round((score / len(questions)) * 100, 2),
        'results': results
    })

@app.route('/health')
def health():
    """Health check endpoint for keep-alive"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
