import os
import json
import random
import re
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# Prevent caching of sensitive pages
@app.after_request
def add_no_cache_headers(response):
    """Add headers to prevent caching of sensitive pages"""
    if request.endpoint in ['login', 'quiz', 'get_questions']:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
PRIVATE_REPO = os.environ.get('PRIVATE_REPO')  # Format: username/repo-name

# Quiz configuration (customizable)
QUIZ_NUM_QUESTIONS = int(os.environ.get('QUIZ_NUM_QUESTIONS', '30'))  # Total questions per quiz
QUIZ_TIME_MINUTES = int(os.environ.get('QUIZ_TIME_MINUTES', '30'))  # Quiz duration in minutes
QUIZ_SECTION1_PERCENTAGE = float(os.environ.get('QUIZ_SECTION1_PERCENTAGE', '0.5'))  # 50% from Section 1

def upload_to_github(filename, content, message="Update file"):
    """Upload/update file in private GitHub repository"""
    print(f"[GITHUB] Uploading {filename} to GitHub...")
    
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{filename}"
    auth_prefix = 'Bearer' if GITHUB_TOKEN.startswith('github_pat_') else 'token'
    
    headers = {
        'Authorization': f'{auth_prefix} {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Check if file exists (to get SHA for update)
    response = requests.get(url, headers=headers)
    
    content_encoded = base64.b64encode(content.encode()).decode()
    
    data = {
        'message': message,
        'content': content_encoded
    }
    
    if response.status_code == 200:
        # File exists, need SHA to update
        data['sha'] = response.json()['sha']
        print(f"[GITHUB] File exists, updating...")
    else:
        print(f"[GITHUB] File doesn't exist, creating...")
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        print(f"[GITHUB] Successfully uploaded {filename}")
        return True
    else:
        print(f"[GITHUB] Failed to upload {filename}: {response.status_code}")
        print(f"[GITHUB] Response: {response.text[:200]}")
        return False

def fetch_from_github(filename, branch='main'):
    """Fetch file content from private GitHub repository"""
    print(f"[DEBUG] fetch_from_github called for: {filename} (branch: {branch})")
    
    if not GITHUB_TOKEN:
        print("[ERROR] GITHUB_TOKEN is not set!")
        raise Exception("GitHub credentials not configured: GITHUB_TOKEN missing")
    
    if not PRIVATE_REPO:
        print("[ERROR] PRIVATE_REPO is not set!")
        raise Exception("GitHub credentials not configured: PRIVATE_REPO missing")
    
    print(f"[DEBUG] GITHUB_TOKEN exists: {GITHUB_TOKEN[:10]}... (truncated)")
    print(f"[DEBUG] PRIVATE_REPO: {PRIVATE_REPO}")
    
    # Try with specified branch
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{filename}?ref={branch}"
    print(f"[DEBUG] Fetching URL: {url}")
    
    # Fine-grained tokens use 'Bearer', classic tokens use 'token'
    # Try Bearer first (for fine-grained tokens)
    auth_prefix = 'Bearer' if GITHUB_TOKEN.startswith('github_pat_') else 'token'
    print(f"[DEBUG] Using auth prefix: {auth_prefix}")
    
    headers = {
        'Authorization': f'{auth_prefix} {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    print(f"[DEBUG] Request headers set (Authorization: {auth_prefix} {GITHUB_TOKEN[:10]}...)")
    
    print(f"[DEBUG] Making GET request...")
    response = requests.get(url, headers=headers)
    print(f"[DEBUG] Response status code: {response.status_code}")
    
    if response.status_code == 200:
        print(f"[DEBUG] Successfully fetched {filename}, size: {len(response.text)} bytes")
        return response.text
    elif response.status_code == 404 and branch == 'main':
        # Try with 'master' branch
        print(f"[DEBUG] 404 on 'main' branch, trying 'master' branch...")
        return fetch_from_github(filename, branch='master')
    else:
        print(f"[ERROR] Failed to fetch {filename}")
        print(f"[ERROR] Status code: {response.status_code}")
        print(f"[ERROR] Response body: {response.text[:500]}")
        raise Exception(f"Failed to fetch {filename}: {response.status_code}")

def verify_github_access():
    """Verify GitHub API access and list repo contents"""
    print("[VERIFY] Testing GitHub API access...")
    
    # Test 1: Check if we can access the repo at all
    repo_url = f"https://api.github.com/repos/{PRIVATE_REPO}"
    headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}' if GITHUB_TOKEN.startswith('github_pat_') else f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    print(f"[VERIFY] Checking repo access: {repo_url}")
    response = requests.get(repo_url, headers=headers)
    print(f"[VERIFY] Repo access status: {response.status_code}")
    
    if response.status_code == 200:
        repo_data = response.json()
        print(f"[VERIFY] ✓ Repo found: {repo_data.get('name')}")
        print(f"[VERIFY] ✓ Default branch: {repo_data.get('default_branch')}")
        print(f"[VERIFY] ✓ Private: {repo_data.get('private')}")
    else:
        print(f"[VERIFY] ✗ Cannot access repo: {response.text[:200]}")
        return False
    
    # Test 2: List root contents
    contents_url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents"
    print(f"[VERIFY] Listing repo contents: {contents_url}")
    response = requests.get(contents_url, headers=headers)
    print(f"[VERIFY] Contents list status: {response.status_code}")
    
    if response.status_code == 200:
        contents = response.json()
        print(f"[VERIFY] ✓ Found {len(contents)} items in repo root:")
        for item in contents:
            print(f"[VERIFY]   - {item.get('name')} ({item.get('type')})")
    else:
        print(f"[VERIFY] ✗ Cannot list contents: {response.text[:200]}")
    
    return True

def load_users():
    """Load users from private repository"""
    try:
        print(f"Attempting to fetch users.json from {PRIVATE_REPO}")
        
        # First time? Run verification
        if not hasattr(load_users, '_verified'):
            verify_github_access()
            load_users._verified = True
        
        users_json = fetch_from_github('users.json')
        print(f"Successfully fetched users.json, content length: {len(users_json)}")
        parsed = json.loads(users_json)
        print(f"Parsed {len(parsed.get('users', []))} users")
        return parsed
    except Exception as e:
        print(f"Error loading users: {e}")
        import traceback
        traceback.print_exc()
        return {"users": []}

def load_used_credentials():
    """Load list of used credentials from GitHub"""
    try:
        content = fetch_from_github('used_credentials.json')
        return json.loads(content)
    except Exception as e:
        print(f"[CREDENTIAL] No existing credentials file or error: {e}")
        return []

def mark_credential_used(username):
    """Mark a credential as used and save to GitHub"""
    used_creds = load_used_credentials()
    
    if username not in used_creds:
        used_creds.append(username)
        content = json.dumps(used_creds, indent=2)
        upload_to_github('used_credentials.json', content, f"Mark {username} as used")
        print(f"[CREDENTIAL] Marked username '{username}' as used")

def is_credential_used(username):
    """Check if credential has been used"""
    used_creds = load_used_credentials()
    return username in used_creds

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
                    'text': match.group(2).strip()  # Ensure clean text without extra spaces
                })
        elif not line_stripped.startswith('OPTIONS:') and not in_options and question:
            # Continue question text
            question += ' ' + line_stripped
    
    # Convert answer numbers to actual option texts
    answer_nums = answer.split()
    correct_option_texts = []
    for num in answer_nums:
        for opt in options:
            if opt['num'] == num:
                correct_option_texts.append(opt['text'].strip())  # Ensure clean text
                break
    
    # Check if any option references other options (e.g., "Both 1 and 2", "Option A and B")
    # If so, don't shuffle to avoid breaking references
    has_references = False
    reference_patterns = [
        r'both.*\d+.*\d+',  # "Both 1 and 2"
        r'both.*and',  # "Both A and B"
        r'option.*and.*option',  # "Option A and Option B"
        r'\d+.*and.*\d+',  # "1 and 2"
        r'all of the above',
        r'none of the above',
        r'all the above',
        r'none the above'
    ]
    
    for opt in options:
        opt_lower = opt['text'].lower()
        if any(re.search(pattern, opt_lower) for pattern in reference_patterns):
            has_references = True
            break
    
    # If no references, shuffle normally but keep special options at end
    if not has_references:
        special_keywords = ['all of the above', 'none of the above', 'all the above', 'none the above']
        
        regular_options = []
        special_options = []
        
        for opt in options:
            if any(keyword in opt['text'].lower() for keyword in special_keywords):
                special_options.append(opt)
            else:
                regular_options.append(opt)
        
        # Shuffle only regular options
        random.shuffle(regular_options)
        
        # Combine: shuffled regular options + special options at end
        shuffled_options = regular_options + special_options
    else:
        # Don't shuffle if options reference each other
        shuffled_options = options
    
    return {
        'number': question_num,
        'question': question.strip(),
        'options': shuffled_options,
        'correct_answers': correct_option_texts,  # Store actual text of correct answers
        'is_multiple': len(correct_option_texts) > 1  # Flag for radio vs checkbox
    }

def generate_random_questions(num_questions=None):
    """Generate random questions with configurable percentage from Section 1"""
    if num_questions is None:
        num_questions = QUIZ_NUM_QUESTIONS
    
    database_content = load_database()
    sections, questions = parse_database(database_content)
    
    if not sections or not questions:
        return []
    
    # Allocate configured percentage to Section 1
    questions_from_section1 = min(round(num_questions * QUIZ_SECTION1_PERCENTAGE), sections[0]['count'])
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
    """Save quiz result to GitHub"""
    result = {
        'username': username,
        'score': score,
        'total': total,
        'percentage': round((score / total) * 100, 2) if total > 0 else 0,
        'time_taken': time_taken,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Load existing results from GitHub
    results = []
    try:
        content = fetch_from_github('results.json')
        results = json.loads(content)
    except Exception as e:
        print(f"[RESULTS] No existing results file or error: {e}")
        results = []
    
    # Append new result
    results.append(result)
    
    # Save back to GitHub
    content = json.dumps(results, indent=2)
    upload_to_github('results.json', content, f"Add result for {username}")

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
        
        print(f"[LOGIN] Login attempt - Username: '{username}'")
        
        # Load users
        print(f"[LOGIN] Loading users from GitHub...")
        users_data = load_users()
        users = users_data.get('users', [])
        
        print(f"[LOGIN] Loaded {len(users)} users from database")
        print(f"[LOGIN] Available usernames: {[u.get('username') for u in users]}")
        
        # Find user
        user = next((u for u in users if u['username'] == username), None)
        
        if user:
            print(f"[LOGIN] User '{username}' found in database")
            print(f"[LOGIN] Stored password: '{user['password']}'")
            print(f"[LOGIN] Provided password: '{password}'")
            
            # Verify password (plain text comparison)
            if user['password'] == password:
                print(f"[LOGIN] Password match!")
                
                # Check if user allows multiple logins (default: False for single use)
                multi_login = user.get('multiLogin', False)
                print(f"[LOGIN] MultiLogin enabled: {multi_login}")
                
                if not multi_login:
                    # Check if credential already used
                    if is_credential_used(username):
                        print(f"[LOGIN] Credential '{username}' already used - login denied")
                        return jsonify({'success': False, 'error': 'This credential has already been used'}), 403
                
                # Login successful
                print(f"[LOGIN] Login successful for '{username}'")
                session.clear()  # Clear any old session data
                session['username'] = username
                session['multi_login'] = multi_login
                session.permanent = True  # Use permanent session with timeout
                
                # Don't mark as used yet - wait until quiz is submitted
                
                return jsonify({'success': True})
            else:
                print(f"[LOGIN] Password mismatch for '{username}'")
        else:
            print(f"[LOGIN] User '{username}' NOT found in database")
        
        print(f"[LOGIN] Login failed for '{username}'")
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()  # Clear entire session
    response = redirect(url_for('login'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/quiz')
def quiz():
    """Quiz page"""
    if 'username' not in session:
        session.clear()  # Clear any stale session data
        return redirect(url_for('login'))
    
    # Check if quiz was already taken (prevent refresh after submission)
    if session.get('quiz_completed', False):
        print(f"[QUIZ] User {session['username']} tried to access quiz after completion - redirecting to login")
        session.clear()
        return redirect(url_for('login'))
    
    # Generate new questions for this session only if not already generated
    if 'questions' not in session or 'quiz_started' not in session:
        questions = generate_random_questions()
        session['questions'] = questions
        session['quiz_started'] = True
        session['start_time'] = datetime.now().isoformat()
        session.modified = True  # Mark session as modified
    
    return render_template('quiz.html', 
                         username=session['username'],
                         quiz_time_minutes=QUIZ_TIME_MINUTES,
                         num_questions=QUIZ_NUM_QUESTIONS)

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
            'options': q['options'],
            'is_multiple': q.get('is_multiple', False)  # Tell frontend if multiple answers allowed
        })
    
    return jsonify({
        'questions': questions_without_answers,
        'quiz_time_minutes': QUIZ_TIME_MINUTES
    })

@app.route('/api/config')
def get_config():
    """API endpoint to get quiz configuration"""
    return jsonify({
        'num_questions': QUIZ_NUM_QUESTIONS,
        'time_minutes': QUIZ_TIME_MINUTES,
        'section1_percentage': QUIZ_SECTION1_PERCENTAGE
    })

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
        correct_answer_texts = q['correct_answers']  # List of correct option texts
        user_answer_texts = user_answers.get(q_id, [])  # List of selected option texts
        
        # Ensure user_answer_texts is a list
        if not isinstance(user_answer_texts, list):
            user_answer_texts = [user_answer_texts] if user_answer_texts else []
        
        # Normalize texts by stripping whitespace for comparison
        correct_set = set(text.strip() for text in correct_answer_texts)
        user_set = set(text.strip() for text in user_answer_texts if text)
        
        is_correct = correct_set == user_set
        if is_correct:
            score += 1
        
        results.append({
            'id': q['id'],
            'question': q['question'],
            'options': q['options'],
            'correct_answers': correct_answer_texts,
            'user_answers': user_answer_texts,
            'is_correct': is_correct,
            'is_multiple': q.get('is_multiple', False)
        })
    
    # Save result to persistent storage
    save_result(session['username'], score, len(questions), time_taken)
    
    # Mark quiz as completed to prevent refresh/retake
    session['quiz_completed'] = True
    
    # Mark credential as used if single-use (after successful submission)
    username = session.get('username')
    multi_login = session.get('multi_login', False)
    if not multi_login and username:
        mark_credential_used(username)
        print(f"[SUBMIT] Single-use credential '{username}' marked as used after quiz submission")
    
    session.modified = True
    
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
    print("="*50)
    print("[STARTUP] Application starting...")
    print(f"[STARTUP] Environment variables check:")
    print(f"  - SECRET_KEY: {'SET' if os.environ.get('SECRET_KEY') else 'NOT SET'}")
    print(f"  - GITHUB_TOKEN: {'SET' if os.environ.get('GITHUB_TOKEN') else 'NOT SET'}")
    print(f"  - PRIVATE_REPO: {os.environ.get('PRIVATE_REPO', 'NOT SET')}")
    print(f"  - QUIZ_NUM_QUESTIONS: {QUIZ_NUM_QUESTIONS}")
    print(f"  - QUIZ_TIME_MINUTES: {QUIZ_TIME_MINUTES}")
    print("="*50)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
