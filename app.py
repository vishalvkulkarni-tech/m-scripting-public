import os
import json
import random
import re
import base64
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# In-memory cache for questions (to avoid session size limits)
# Key: session_id, Value: {'questions': [...], 'timestamp': datetime, 'database_key': str}
questions_cache = {}

def cleanup_old_cache():
    """Remove cache entries older than 2 hours"""
    cutoff = datetime.now() - timedelta(hours=2)
    to_remove = [k for k, v in questions_cache.items() if v.get('timestamp', datetime.min) < cutoff]
    for key in to_remove:
        del questions_cache[key]
    if to_remove:
        print(f"[CACHE] Cleaned up {len(to_remove)} old cache entries")

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
QUIZ_NUM_QUESTIONS = int(os.environ.get('QUIZ_NUM_QUESTIONS', '30'))  # Total questions per quiz (global default)
QUIZ_TIME_MINUTES = int(os.environ.get('QUIZ_TIME_MINUTES', '30'))  # Quiz duration in minutes (global default)

# Database-specific quiz configuration (overrides global defaults if set)
MDB_NUM_QUESTIONS = os.environ.get('MDB_NUM_QUESTIONS')  # MATLAB Scripting Database
MDB_TIME_MINUTES = os.environ.get('MDB_TIME_MINUTES')
SLDB_NUM_QUESTIONS = os.environ.get('SLDB_NUM_QUESTIONS')  # Simulink & Stateflow Database
SLDB_TIME_MINUTES = os.environ.get('SLDB_TIME_MINUTES')
SLMDB_NUM_QUESTIONS = os.environ.get('SLMDB_NUM_QUESTIONS')  # Simulink & Stateflow Modeling Database
SLMDB_TIME_MINUTES = os.environ.get('SLMDB_TIME_MINUTES')
EMBCDB_NUM_QUESTIONS = os.environ.get('EMBCDB_NUM_QUESTIONS')  # Embedded C Database (future)
EMBCDB_TIME_MINUTES = os.environ.get('EMBCDB_TIME_MINUTES')
CANDB_NUM_QUESTIONS = os.environ.get('CANDB_NUM_QUESTIONS')  # CAN Database
CANDB_TIME_MINUTES = os.environ.get('CANDB_TIME_MINUTES')
AUTOSARDB_NUM_QUESTIONS = os.environ.get('AUTOSARDB_NUM_QUESTIONS')  # AUTOSAR Database
AUTOSARDB_TIME_MINUTES = os.environ.get('AUTOSARDB_TIME_MINUTES')

# MATLAB Database Section Percentages (18 sections total, must sum to 1.0 if provided)
MATLAB_SCRIPTING_FUNDAMENTALS_PCT = os.environ.get('MATLAB_SCRIPTING_FUNDAMENTALS_PCT')
MATLAB_SCRIPTING_ADVANCED_PCT = os.environ.get('MATLAB_SCRIPTING_ADVANCED_PCT')
MATLAB_SCRIPTING_TRICKY_PCT = os.environ.get('MATLAB_SCRIPTING_TRICKY_PCT')
MATLAB_WORKSPACE_SCOPE_PCT = os.environ.get('MATLAB_WORKSPACE_SCOPE_PCT')
MATLAB_SIMPLE_TRICKY_PCT = os.environ.get('MATLAB_SIMPLE_TRICKY_PCT')
SIMULINK_MSCRIPT_FUNDAMENTALS_PCT = os.environ.get('SIMULINK_MSCRIPT_FUNDAMENTALS_PCT')
SIMULINK_MSCRIPT_SIMPLE_PCT = os.environ.get('SIMULINK_MSCRIPT_SIMPLE_PCT')
SIMULINK_MSCRIPT_TRICKY_PCT = os.environ.get('SIMULINK_MSCRIPT_TRICKY_PCT')
FIND_SYSTEM_COMMAND_PCT = os.environ.get('FIND_SYSTEM_COMMAND_PCT')
SIMULINK_TRUEFALSE_PCT = os.environ.get('SIMULINK_TRUEFALSE_PCT')
MATLAB_TRUEFALSE_PCT = os.environ.get('MATLAB_TRUEFALSE_PCT')
STATEFLOW_MSCRIPTING_PCT = os.environ.get('STATEFLOW_MSCRIPTING_PCT')
SIMULINK_DATA_DICTIONARY_PCT = os.environ.get('SIMULINK_DATA_DICTIONARY_PCT')
MODEL_COMPARISON_PROJECTS_PCT = os.environ.get('MODEL_COMPARISON_PROJECTS_PCT')
CODE_GENERATION_SCRIPTING_PCT = os.environ.get('CODE_GENERATION_SCRIPTING_PCT')
TEST_AUTOMATION_PCT = os.environ.get('TEST_AUTOMATION_PCT')
SIMULINK_DATA_HANDLING_PCT = os.environ.get('SIMULINK_DATA_HANDLING_PCT')
MISCELLANEOUS_MSCRIPTING_PCT = os.environ.get('MISCELLANEOUS_MSCRIPTING_PCT')

# Simulink-Stateflow Database Section Percentages (8 sections total, must sum to 1.0 if provided)
SIMULINK_BASIC_PCT = os.environ.get('SIMULINK_BASIC_PCT')  # SIMULINK BASIC
SIMULINK_ADVANCED_PCT = os.environ.get('SIMULINK_ADVANCED_PCT')  # SIMULINK ADVANCED
SIMULINK_SUPER_ADVANCED_PCT = os.environ.get('SIMULINK_SUPER_ADVANCED_PCT')  # SIMULINK SUPER ADVANCED
STATEFLOW_BASIC_PCT = os.environ.get('STATEFLOW_BASIC_PCT')  # STATEFLOW BASIC
STATEFLOW_ADVANCED_PCT = os.environ.get('STATEFLOW_ADVANCED_PCT')  # STATEFLOW ADVANCED
STATEFLOW_SUPER_ADVANCED_PCT = os.environ.get('STATEFLOW_SUPER_ADVANCED_PCT')  # STATEFLOW SUPER ADVANCED
STATEFLOW_TRICKY_PCT = os.environ.get('STATEFLOW_TRICKY_PCT')  # STATEFLOW TRICKY
SIMULINK_TRICKY_PCT = os.environ.get('SIMULINK_TRICKY_PCT')  # SIMULINK TRICKY

# Simulink-Stateflow Modeling Database Section Percentages (4 sections total, must sum to 1.0 if provided)
MODELING_SIMULINK_BASIC_PCT = os.environ.get('MODELING_SIMULINK_BASIC_PCT')  # SIMULINK MODELING BASICS
MODELING_SIMULINK_ADVANCED_PCT = os.environ.get('MODELING_SIMULINK_ADVANCED_PCT')  # SIMULINK MODELING ADVANCED
MODELING_STATEFLOW_BASIC_PCT = os.environ.get('MODELING_STATEFLOW_BASIC_PCT')  # STATEFLOW MODELING BASICS
MODELING_STATEFLOW_ADVANCED_PCT = os.environ.get('MODELING_STATEFLOW_ADVANCED_PCT')  # STATEFLOW MODELING ADVANCED

# Embedded C Automotive Database Section Percentages (6 sections total, must sum to 1.0 if provided)
BASIC_EMBEDDED_C_PCT = os.environ.get('BASIC_EMBEDDED_C_PCT')  # BASIC EMBEDDED C
ADVANCED_EMBEDDED_C_PCT = os.environ.get('ADVANCED_EMBEDDED_C_PCT')  # ADVANCED EMBEDDED C
AUTOMOTIVE_EMBEDDED_C_PCT = os.environ.get('AUTOMOTIVE_EMBEDDED_C_PCT')  # AUTOMOTIVE EMBEDDED C
MATLAB_AUTO_CODE_GENERATION_PCT = os.environ.get('MATLAB_AUTO_CODE_GENERATION_PCT')  # MATLAB AUTO CODE GENERATION
TRICKY_EMBEDDED_C_PCT = os.environ.get('TRICKY_EMBEDDED_C_PCT')  # TRICKY EMBEDDED C
MEMORY_RELATED_EMBEDDED_C_PCT = os.environ.get('MEMORY_RELATED_EMBEDDED_C_PCT')  # MEMORY RELATED EMBEDDED C

# CAN Database Section Percentages (3 sections total, must sum to 1.0 if provided)
CAN_HIGH_LEVEL_PCT = os.environ.get('CAN_HIGH_LEVEL_PCT')  # CAN HIGH LEVEL
CAN_FRAME_FORMAT_PCT = os.environ.get('CAN_FRAME_FORMAT_PCT')  # CAN FRAME FORMAT
MISC_CAN_PCT = os.environ.get('MISC_CAN_PCT')  # MISC CAN

# AUTOSAR Database Section Percentages (3 sections total, must sum to 1.0 if provided)
CLASSIC_AUTOSAR_PCT = os.environ.get('CLASSIC_AUTOSAR_PCT')  # CLASSIC AUTOSAR
ADAPTIVE_AUTOSAR_PCT = os.environ.get('ADAPTIVE_AUTOSAR_PCT')  # ADAPTIVE AUTOSAR
MISC_AUTOSAR_PCT = os.environ.get('MISC_AUTOSAR_PCT')  # MISC AUTOSAR

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

def load_completed_sections():
    """Load completed sections data from GitHub"""
    try:
        content = fetch_from_github('completed_sections.json')
        return json.loads(content)
    except Exception as e:
        print(f"[SECTIONS] No existing completed sections file or error: {e}")
        return {}

def mark_section_completed(username, database_key, section_name):
    """Mark a section as completed for a user"""
    completed = load_completed_sections()
    
    if username not in completed:
        completed[username] = {}
    
    if database_key not in completed[username]:
        completed[username][database_key] = []
    
    if section_name not in completed[username][database_key]:
        completed[username][database_key].append(section_name)
        content = json.dumps(completed, indent=2)
        upload_to_github('completed_sections.json', content, f"Mark {section_name} completed for {username}")
        print(f"[SECTIONS] Marked section '{section_name}' in '{database_key}' as completed for '{username}'")

def is_section_completed(username, database_key, section_name):
    """Check if section has been completed by user"""
    completed = load_completed_sections()
    return section_name in completed.get(username, {}).get(database_key, [])

def get_available_databases():
    """Get list of available quiz databases with numeric IDs and hardcoded filenames"""
    databases = {
        'db1': {'file': 'm_script_database.txt', 'name': 'MATLAB Scripting', 'index': 1},
        'db2': {'file': 'simulink_stateflow_database.txt', 'name': 'Simulink & Stateflow', 'index': 2},
        'db3': {'file': 'simulink_stateflow_modeling.txt', 'name': 'Simulink & Stateflow Modeling', 'index': 3},
        'db4': {'file': 'embedded_c_automotive.txt', 'name': 'Embedded C Automotive', 'index': 4},
        'db5': {'file': 'CAN.txt', 'name': 'CAN Protocol', 'index': 5},
        'db6': {'file': 'autosar.txt', 'name': 'AUTOSAR', 'index': 6}
    }
    return databases

def get_database_config(database_key):
    """Get configuration (num_questions, time_minutes) for a specific database with fallback logic"""
    # Map database keys to their specific env variables
    db_config_map = {
        'db1': {'num_questions': MDB_NUM_QUESTIONS, 'time_minutes': MDB_TIME_MINUTES},
        'db2': {'num_questions': SLDB_NUM_QUESTIONS, 'time_minutes': SLDB_TIME_MINUTES},
        'db3': {'num_questions': SLMDB_NUM_QUESTIONS, 'time_minutes': SLMDB_TIME_MINUTES},
        'db4': {'num_questions': EMBCDB_NUM_QUESTIONS, 'time_minutes': EMBCDB_TIME_MINUTES},
        'db5': {'num_questions': CANDB_NUM_QUESTIONS, 'time_minutes': CANDB_TIME_MINUTES},
        'db6': {'num_questions': AUTOSARDB_NUM_QUESTIONS, 'time_minutes': AUTOSARDB_TIME_MINUTES}
    }
    
    # Get database-specific config
    db_config = db_config_map.get(database_key, {})
    
    # Determine num_questions with fallback logic
    if db_config.get('num_questions') is not None:
        num_questions = int(db_config['num_questions'])
        print(f"[CONFIG] Using database-specific num_questions for {database_key}: {num_questions}")
    else:
        num_questions = QUIZ_NUM_QUESTIONS
        print(f"[CONFIG] Using global QUIZ_NUM_QUESTIONS for {database_key}: {num_questions}")
    
    # Determine time_minutes with fallback logic
    if db_config.get('time_minutes') is not None:
        time_minutes = int(db_config['time_minutes'])
        print(f"[CONFIG] Using database-specific time_minutes for {database_key}: {time_minutes}")
    else:
        time_minutes = QUIZ_TIME_MINUTES
        print(f"[CONFIG] Using global QUIZ_TIME_MINUTES for {database_key}: {time_minutes}")
    
    return {
        'num_questions': num_questions,
        'time_minutes': time_minutes
    }

def load_database(database_key='db1'):
    """Load question database from private repository with hardcoded filenames"""
    try:
        databases = get_available_databases()
        if database_key not in databases:
            print(f"[WARNING] Unknown database_key '{database_key}', falling back to 'db1'")
            database_key = 'db1'  # Default fallback
        
        db_info = databases[database_key]
        filename = db_info['file']
        db_index = db_info['index']
        
        print(f"[DATABASE] Loading database #{db_index}: '{database_key}' from file: {filename}")
        content = fetch_from_github(filename)
        print(f"[DATABASE] Loaded {len(content)} bytes from {filename}")
        print(f"[DATABASE] Database index: {db_index}, Key: {database_key}, Name: {db_info['name']}")
        return content
    except Exception as e:
        print(f"[ERROR] Error loading database '{database_key}': {e}")
        return ""

def parse_database(content):
    """Parse database file to extract sections and questions with fallback logic"""
    # Try primary parsing method (line-by-line)
    sections, questions = _parse_database_line_by_line(content)
    
    # Safeguard: If no questions found, try alternative parsing method
    if not questions or len(questions) == 0:
        print("[WARNING] Primary parser found 0 questions. Trying fallback parser...")
        sections, questions = _parse_database_fallback(content)
        if questions:
            print(f"[SUCCESS] Fallback parser found {len(questions)} questions")
    
    return sections, questions

def _parse_database_line_by_line(content):
    """Primary parsing method: line-by-line"""
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

def _parse_database_fallback(content):
    """Fallback parsing method: split by QUESTION markers"""
    sections = []
    questions = []
    
    # Split content into section blocks
    section_blocks = re.split(r'\nSECTION:\s*', content)
    
    for block in section_blocks:
        if not block.strip():
            continue
        
        # First line is section name
        lines = block.split('\n')
        section_name = lines[0].strip()
        
        if not section_name:
            continue
        
        current_section = {'name': section_name, 'count': 0, 'question_indices': []}
        
        # Split by QUESTION markers (but keep the QUESTION keyword)
        question_blocks = re.split(r'(\nQUESTION\s+\d+\.)', block)
        
        # Reconstruct questions (pairs of marker + content)
        for i in range(1, len(question_blocks), 2):
            if i + 1 < len(question_blocks):
                question_text = (question_blocks[i].strip() + '\n' + question_blocks[i + 1]).strip()
                
                # Validate it has required components
                if 'OPTIONS:' in question_text and 'ANSWER:' in question_text:
                    questions.append(question_text)
                    current_section['count'] += 1
                    current_section['question_indices'].append(len(questions) - 1)
        
        if current_section['count'] > 0:
            sections.append(current_section)
    
    return sections, questions

def parse_question(question_text):
    """Parse individual question to extract components with detailed logging"""
    lines = question_text.split('\n')
    question_num = ''
    question = ''
    options = []
    answer = ''
    
    in_options = False
    line_count = 0
    options_line_found = False
    
    print(f"[PARSE_DEBUG] Starting to parse question with {len(lines)} lines")
    
    for line in lines:
        line_count += 1
        line_stripped = line.strip()
        
        if line_stripped.startswith('QUESTION '):
            # Extract question number and text
            match = re.match(r'QUESTION (\d+)\.\s*(.*)', line_stripped)
            if match:
                question_num = match.group(1)
                question = match.group(2)
                print(f"[PARSE_DEBUG] Line {line_count}: Found QUESTION {question_num}, initial text: '{match.group(2)[:50]}'")
        elif line_stripped.startswith('OPTIONS:'):
            in_options = True
            options_line_found = True
            print(f"[PARSE_DEBUG] Line {line_count}: Found OPTIONS marker, question text length: {len(question)}")
        elif line_stripped.startswith('ANSWER:'):
            in_options = False
            answer = line_stripped[7:].strip()
            print(f"[PARSE_DEBUG] Line {line_count}: Found ANSWER: {answer}, parsed {len(options)} options")
        elif in_options and line_stripped:
            # Parse option (format: "1. option text")
            match = re.match(r'(\d+)\.\s*(.*)', line_stripped)
            if match:
                options.append({
                    'num': match.group(1),
                    'text': match.group(2).strip()
                })
                print(f"[PARSE_DEBUG] Line {line_count}: Parsed option {match.group(1)}: '{match.group(2)[:30]}'")
            else:
                print(f"[PARSE_DEBUG] Line {line_count}: In options but line doesn't match pattern: '{line_stripped[:50]}'")
        elif not line_stripped.startswith('OPTIONS:') and not in_options and question:
            # Continue question text - preserve newlines for diagram tags
            question += '\n' + line_stripped
    
    print(f"[PARSE_DEBUG] Parsing complete for Q{question_num}: question_len={len(question)}, options={len(options)}, answer='{answer}'")
    
    # Debug logging for parsing issues
    if not question:
        print(f"[PARSE_ERROR] No question text found in: {question_text[:200]}")
    if not options:
        print(f"[PARSE_ERROR] No options found in question {question_num}, options_line_found={options_line_found}")
        print(f"[PARSE_ERROR] Full question text:\n{question_text}")
    if not answer:
        print(f"[PARSE_ERROR] No answer found in question {question_num}")
    
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

def generate_random_questions(database_key='db1', section_name=None, num_questions=None):
    """Generate random questions with configurable percentage distribution across all sections"""
    if num_questions is None:
        num_questions = QUIZ_NUM_QUESTIONS
    
    # Get database info to determine which one we're loading
    databases = get_available_databases()
    db_index = databases.get(database_key, {}).get('index', 0)
    
    database_content = load_database(database_key)
    
    # Debug: Check what we actually loaded
    content_preview = database_content[:200].replace('\n', ' ') if database_content else '(empty)'
    print(f"[DEBUG] Database #{db_index} - Loaded content preview: {content_preview}")
    
    sections, questions = parse_database(database_content)
    
    print(f"[DEBUG] Database: {database_key} (index #{db_index}), Sections: {len(sections)}, Questions: {len(questions)}")
    if sections:
        for sect in sections:
            print(f"[DEBUG]   Section '{sect['name']}': {sect['count']} questions")
    
    if not sections or not questions:
        print(f"[ERROR] No sections or questions found for database: {database_key} (index #{db_index})")
        return []
    
    # If specific section requested, use only that section
    if section_name and section_name != 'ALL':
        target_section = next((s for s in sections if s['name'] == section_name), None)
        if not target_section:
            return []
        
        available = target_section['question_indices']
        num_to_select = min(num_questions, len(available))
        selected_indices = random.sample(available, num_to_select)
        selected = [questions[idx] for idx in selected_indices]
    else:
        # Get percentage distribution based on database index
        percentages = None
        
        if db_index == 1:  # MATLAB Scripting
            # Try to get percentages from environment variables
            pct_vars = [
                MATLAB_SCRIPTING_FUNDAMENTALS_PCT,
                MATLAB_SCRIPTING_ADVANCED_PCT,
                MATLAB_SCRIPTING_TRICKY_PCT,
                MATLAB_WORKSPACE_SCOPE_PCT,
                MATLAB_SIMPLE_TRICKY_PCT,
                SIMULINK_MSCRIPT_FUNDAMENTALS_PCT,
                SIMULINK_MSCRIPT_SIMPLE_PCT,
                SIMULINK_MSCRIPT_TRICKY_PCT,
                FIND_SYSTEM_COMMAND_PCT,
                SIMULINK_TRUEFALSE_PCT,
                MATLAB_TRUEFALSE_PCT,
                STATEFLOW_MSCRIPTING_PCT,
                SIMULINK_DATA_DICTIONARY_PCT,
                MODEL_COMPARISON_PROJECTS_PCT,
                CODE_GENERATION_SCRIPTING_PCT,
                TEST_AUTOMATION_PCT,
                SIMULINK_DATA_HANDLING_PCT,
                MISCELLANEOUS_MSCRIPTING_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        elif db_index == 2:  # Simulink & Stateflow
            # Try to get percentages from environment variables
            pct_vars = [
                SIMULINK_BASIC_PCT,
                SIMULINK_ADVANCED_PCT,
                SIMULINK_SUPER_ADVANCED_PCT,
                STATEFLOW_BASIC_PCT,
                STATEFLOW_ADVANCED_PCT,
                STATEFLOW_SUPER_ADVANCED_PCT,
                STATEFLOW_TRICKY_PCT,
                SIMULINK_TRICKY_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        elif db_index == 3:  # Simulink & Stateflow Modeling
            # Try to get percentages from environment variables
            pct_vars = [
                MODELING_SIMULINK_BASIC_PCT,
                MODELING_SIMULINK_ADVANCED_PCT,
                MODELING_STATEFLOW_BASIC_PCT,
                MODELING_STATEFLOW_ADVANCED_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        elif db_index == 4:  # Embedded C Automotive
            # Try to get percentages from environment variables
            pct_vars = [
                BASIC_EMBEDDED_C_PCT,
                ADVANCED_EMBEDDED_C_PCT,
                AUTOMOTIVE_EMBEDDED_C_PCT,
                MATLAB_AUTO_CODE_GENERATION_PCT,
                TRICKY_EMBEDDED_C_PCT,
                MEMORY_RELATED_EMBEDDED_C_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        elif db_index == 5:  # CAN Protocol
            # Try to get percentages from environment variables
            pct_vars = [
                CAN_HIGH_LEVEL_PCT,
                CAN_FRAME_FORMAT_PCT,
                MISC_CAN_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        elif db_index == 6:  # AUTOSAR
            # Try to get percentages from environment variables
            pct_vars = [
                CLASSIC_AUTOSAR_PCT,
                ADAPTIVE_AUTOSAR_PCT,
                MISC_AUTOSAR_PCT
            ]
            if any(p is not None for p in pct_vars):
                # At least one variable is set, use them (convert None to 0.0)
                percentages = [float(p) if p is not None else 0.0 for p in pct_vars]
        
        # If no percentages configured or database not recognized, use equal distribution
        if percentages is None:
            num_sections = len(sections)
            percentages = [1.0 / num_sections] * num_sections
            print(f"[QUIZ] No custom percentages found for {database_key}. Using equal distribution.")
        
        # Ensure we have the right number of percentages
        elif len(percentages) != len(sections):
            print(f"[WARNING] Percentage count mismatch for {database_key}. Using equal distribution.")
            num_sections = len(sections)
            percentages = [1.0 / num_sections] * num_sections
        
        # Validate that percentages sum to approximately 1.0 (allow small floating point errors)
        else:
            total_pct = sum(percentages)
            if abs(total_pct - 1.0) > 0.01:  # More than 1% deviation
                print(f"[WARNING] Percentages sum to {total_pct} (expected 1.0) for {database_key}. Using equal distribution.")
                num_sections = len(sections)
                percentages = [1.0 / num_sections] * num_sections
        
        # Calculate questions per section based on percentages
        questions_per_section = [round(num_questions * pct) for pct in percentages]
        
        # Adjust for rounding errors to ensure total equals num_questions
        current_total = sum(questions_per_section)
        if current_total < num_questions:
            # Add extra questions to sections with highest percentages
            diff = num_questions - current_total
            sorted_indices = sorted(range(len(percentages)), key=lambda i: percentages[i], reverse=True)
            for i in range(diff):
                questions_per_section[sorted_indices[i % len(sorted_indices)]] += 1
        elif current_total > num_questions:
            # Remove questions from sections with lowest percentages
            diff = current_total - num_questions
            sorted_indices = sorted(range(len(percentages)), key=lambda i: percentages[i])
            for i in range(diff):
                if questions_per_section[sorted_indices[i % len(sorted_indices)]] > 0:
                    questions_per_section[sorted_indices[i % len(sorted_indices)]] -= 1
        
        # Select random questions from each section
        selected = []
        for i, section in enumerate(sections):
            if questions_per_section[i] > 0:
                available = section['question_indices']
                num_to_select = min(questions_per_section[i], len(available))
                selected_indices = random.sample(available, num_to_select)
                
                for idx in selected_indices:
                    selected.append(questions[idx])
        
        print(f"[QUIZ] Distribution for {database_key}: {dict(zip([s['name'] for s in sections], questions_per_section))}")
    
    # Shuffle questions
    random.shuffle(selected)
    print(f"[QUIZ] Selected {len(selected)} raw question texts")
    
    # Parse each question
    parsed_questions = []
    failed_count = 0
    
    for i, q_text in enumerate(selected):
        try:
            parsed = parse_question(q_text)
            
            # Validate parsed question has required fields
            if not parsed.get('question') or not parsed.get('options') or not parsed.get('correct_answers'):
                print(f"[ERROR] Q{i+1} missing required fields: question={bool(parsed.get('question'))}, options={len(parsed.get('options', []))}, answers={len(parsed.get('correct_answers', []))}")
                print(f"[ERROR] Raw question text (first 200 chars): {q_text[:200]}")
                failed_count += 1
                continue
            
            parsed['id'] = i + 1
            parsed_questions.append(parsed)
            
            # Log first question from each section (for debugging)
            if i < 4:
                question_preview = parsed['question'][:100].replace('\n', ' ')
                print(f"[QUIZ] Sample Q{i+1}: {question_preview}... (options: {len(parsed['options'])}, correct: {len(parsed['correct_answers'])})")
        
        except Exception as e:
            print(f"[ERROR] Failed to parse question {i+1}: {e}")
            print(f"[ERROR] Raw question text (first 200 chars): {q_text[:200]}")
            failed_count += 1
            continue
    
    print(f"[QUIZ] Parsed {len(parsed_questions)} questions successfully, {failed_count} failed")
    
    if len(parsed_questions) == 0:
        print(f"[ERROR] No questions were successfully parsed! Check parse_question logic.")
    
    return parsed_questions

def save_result(username, score, total, time_taken, database_key=None, section_name=None, section_wise_scores=None):
    """Save quiz result to GitHub with detailed section information"""
    result = {
        'username': username,
        'database': database_key or 'unknown',
        'section': section_name or 'All Sections',
        'score': score,
        'total': total,
        'percentage': round((score / total) * 100, 2) if total > 0 else 0,
        'time_taken': time_taken,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'section_wise_scores': section_wise_scores or {}
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
    """Landing page - redirect to login or section selection"""
    if 'username' in session:
        return redirect(url_for('select_section'))
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
                    # Check if any database has been completed (credential already used)
                    completed = load_completed_sections()
                    user_completed = completed.get(username, {})
                    if any('ALL' in sections for sections in user_completed.values()):
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

@app.route('/select-section')
def select_section():
    """Section selection page"""
    if 'username' not in session:
        session.clear()
        return redirect(url_for('login'))
    
    # Load available databases
    databases = get_available_databases()
    
    # Get completed databases for user
    username = session['username']
    multi_login = session.get('multi_login', False)
    completed_databases = []
    
    if not multi_login:
        for db_key in databases.keys():
            if is_section_completed(username, db_key, 'ALL'):
                completed_databases.append(db_key)
    
    return render_template('select_section.html',
                         username=username,
                         databases=databases,
                         completed=completed_databases,
                         multi_login=multi_login)

@app.route('/quiz')
def quiz():
    """Quiz page"""
    if 'username' not in session:
        session.clear()  # Clear any stale session data
        return redirect(url_for('login'))
    
    # Get database from query params
    database_key = request.args.get('database', 'db1')
    print(f"[QUIZ] Requested database_key: '{database_key}' from URL: {request.url}")
    
    # Get database info
    databases = get_available_databases()
    db_index = databases.get(database_key, {}).get('index', 0)
    print(f"[QUIZ] Database index: {db_index}")
    
    # Check if database already completed (for non-multi-login users)
    multi_login = session.get('multi_login', False)
    if not multi_login:
        if is_section_completed(session['username'], database_key, 'ALL'):
            print(f"[QUIZ] Database '{database_key}' already completed by {session['username']}")
            return redirect(url_for('select_section'))
    
    # Check if quiz was already taken (prevent refresh after submission)
    if session.get('quiz_completed', False):
        print(f"[QUIZ] User {session['username']} tried to access quiz after completion - redirecting to section selection")
        session.pop('quiz_completed', None)
        return redirect(url_for('select_section'))
    
    # Clear cache and generate new questions if database changed
    if session.get('database_key') != database_key:
        print(f"[QUIZ] Database changed from '{session.get('database_key')}' to '{database_key}' - clearing cache")
        # Clear quiz-related session data and cache
        old_session_id = session.get('quiz_session_id')
        if old_session_id and old_session_id in questions_cache:
            del questions_cache[old_session_id]
            print(f"[QUIZ] Removed old cache entry: {old_session_id}")
        
        session.pop('quiz_session_id', None)
        session.pop('quiz_started', None)
        session.pop('start_time', None)
        session.pop('quiz_completed', None)
        session.modified = True
    
    # Get database-specific configuration
    db_config = get_database_config(database_key)
    num_questions = db_config['num_questions']
    time_minutes = db_config['time_minutes']
    
    # Generate new questions for this session only if not already generated
    if 'questions' not in session or 'quiz_started' not in session:
        # Generate questions from ALL sections in the database with distribution
        print(f"[QUIZ] Generating new questions for database: {database_key} (index #{db_index})")
        questions = generate_random_questions(database_key, section_name=None, num_questions=num_questions)
        
        if not questions:
            print(f"[ERROR] No questions generated for database {database_key}")
            return redirect(url_for('select_section'))
        
        print(f"[QUIZ] Generated {len(questions)} questions")
        
        # Generate unique session ID for this quiz session
        if 'quiz_session_id' not in session:
            session['quiz_session_id'] = str(uuid.uuid4())
        
        quiz_session_id = session['quiz_session_id']
        
        # Store questions in memory cache instead of session (to avoid size limits)
        cleanup_old_cache()  # Clean up old entries first
        questions_cache[quiz_session_id] = {
            'questions': questions,
            'timestamp': datetime.now(),
            'database_key': database_key
        }
        
        # Store only metadata in session
        session['database_key'] = database_key
        session['section_name'] = 'ALL'
        session['quiz_started'] = True
        session['start_time'] = datetime.now().isoformat()
        session.modified = True
        
        print(f"[QUIZ] Stored {len(questions)} questions in cache with ID: {quiz_session_id}")
        print(f"[QUIZ] Cache now has {len(questions_cache)} entries")
    else:
        print(f"[QUIZ] Reusing existing questions for database: {database_key} (index #{db_index})")
    
    databases = get_available_databases()
    db_name = databases.get(database_key, {}).get('name', 'Quiz')
    
    return render_template('quiz.html', 
                         username=session['username'],
                         quiz_name=db_name,
                         quiz_time_minutes=time_minutes,
                         num_questions=num_questions)

@app.route('/api/questions')
def get_questions():
    """API endpoint to get questions"""
    if 'username' not in session:
        print("[API] /api/questions - No username in session")
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get questions from cache using session ID
    quiz_session_id = session.get('quiz_session_id')
    if not quiz_session_id:
        print("[API] /api/questions - No quiz_session_id in session")
        return jsonify({'error': 'No active quiz session'}), 400
    
    cache_entry = questions_cache.get(quiz_session_id)
    if not cache_entry:
        print(f"[API] /api/questions - No cache entry found for session ID: {quiz_session_id}")
        print(f"[API] Available cache keys: {list(questions_cache.keys())}")
        return jsonify({'error': 'Quiz session expired'}), 400
    
    questions = cache_entry.get('questions', [])
    print(f"[API] /api/questions - Retrieved {len(questions)} questions from cache (session: {quiz_session_id})")
    
    if questions:
        # Log first question details
        first_q = questions[0]
        q_preview = first_q.get('question', '')[:100].replace('\n', ' ')
        print(f"[API] First question preview: {q_preview}...")
        print(f"[API] First question has {len(first_q.get('options', []))} options")
    
    # Return questions without answers
    questions_without_answers = []
    for q in questions:
        question_data = {
            'id': q['id'],
            'question': q['question'],
            'options': q['options'],
            'is_multiple': q.get('is_multiple', False)  # Tell frontend if multiple answers allowed
        }
        questions_without_answers.append(question_data)
    
    # Get database-specific configuration
    database_key = cache_entry.get('database_key', 'db1')
    db_config = get_database_config(database_key)
    
    response_data = {
        'questions': questions_without_answers,
        'quiz_time_minutes': db_config['time_minutes']
    }
    
    print(f"[API] Returning {len(questions_without_answers)} questions to frontend")
    print(f"[API] Response size: ~{len(json.dumps(response_data))} bytes")
    
    return jsonify(response_data)

@app.route('/api/config')
def get_config():
    """API endpoint to get quiz configuration"""
    # Get database from session if available
    database_key = session.get('database_key', 'db1')
    db_config = get_database_config(database_key)
    
    return jsonify({
        'num_questions': db_config['num_questions'],
        'time_minutes': db_config['time_minutes']
    })

@app.route('/api/submit', methods=['POST'])
def submit_quiz():
    """Submit quiz and get results"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    user_answers = data.get('answers', {})
    time_taken = data.get('time_taken', '00:00')
    
    # Get questions from cache
    quiz_session_id = session.get('quiz_session_id')
    cache_entry = questions_cache.get(quiz_session_id, {})
    questions = cache_entry.get('questions', [])
    
    database_key = session.get('database_key', 'unknown')
    section_name = session.get('section_name', 'All Sections')
    
    # Load database to get section information for each question
    database_content = load_database(database_key)
    sections, all_questions = parse_database(database_content)
    
    # Create a mapping of question text to section name
    question_to_section = {}
    for section in sections:
        for q_idx in section['question_indices']:
            if q_idx < len(all_questions):
                q_text = all_questions[q_idx]
                # Extract just the question text (after "QUESTION N.")
                match = re.search(r'QUESTION \d+\.\s*(.*?)(?:\nOPTIONS:|\n|$)', q_text, re.DOTALL)
                if match:
                    question_key = match.group(1).strip()[:100]  # First 100 chars as key
                    question_to_section[question_key] = section['name']
    
    # Calculate score and track section-wise performance
    score = 0
    results = []
    section_wise_scores = {}
    
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
        
        # Find which section this question belongs to
        question_key = q['question'].strip()[:100]
        question_section = question_to_section.get(question_key, 'Unknown Section')
        
        # Track section-wise scores
        if question_section not in section_wise_scores:
            section_wise_scores[question_section] = {'correct': 0, 'total': 0}
        
        section_wise_scores[question_section]['total'] += 1
        if is_correct:
            section_wise_scores[question_section]['correct'] += 1
        
        results.append({
            'id': q['id'],
            'question': q['question'],
            'section': question_section,
            'options': q['options'],
            'correct_answers': correct_answer_texts,
            'user_answers': user_answer_texts,
            'is_correct': is_correct,
            'is_multiple': q.get('is_multiple', False)
        })
    
    # Calculate percentages for each section
    section_wise_results = {}
    for sect, scores in section_wise_scores.items():
        section_wise_results[sect] = {
            'correct': scores['correct'],
            'total': scores['total'],
            'percentage': round((scores['correct'] / scores['total']) * 100, 2) if scores['total'] > 0 else 0
        }
    
    # Save result to persistent storage with section details
    save_result(session['username'], score, len(questions), time_taken, 
                database_key, section_name, section_wise_results)
    
    # Mark section as completed if single-use (after successful submission)
    username = session.get('username')
    multi_login = session.get('multi_login', False)
    
    if not multi_login and username and section_name:
        mark_section_completed(username, database_key, section_name)
        print(f"[SUBMIT] Section '{section_name}' in '{database_key}' marked as completed for '{username}'")
    
    # Mark quiz as completed to prevent refresh/retake
    session['quiz_completed'] = True
    session.modified = True
    
    return jsonify({
        'score': score,
        'total': len(questions),
        'percentage': round((score / len(questions)) * 100, 2),
        'results': results,
        'section_wise_scores': section_wise_results
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
