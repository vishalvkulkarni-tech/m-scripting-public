# MATLAB/Simulink M-Scripting Quiz Application

A web-based quiz application for testing MATLAB and Simulink M-Scripting knowledge.

## Features

- 🔐 User authentication
- 📝 30 random questions per quiz (50% from fundamentals)
- ⏱️ 30-minute timer with auto-submit
- ✅ Automatic grading
- 📊 Results storage and history
- 🔄 Keep-alive mechanism (prevents server sleep)
- 📱 Responsive design

## Technology Stack

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **Authentication**: bcrypt
- **Deployment**: Render.com
- **Data Source**: Private GitHub repository

## Setup Instructions

### Prerequisites

1. GitHub account with two repositories:
   - Private repo: Contains question database and user credentials
   - Public repo: Contains this application code

2. Render.com account (free tier)

### Step 1: Prepare Private Repository

Upload to your private repo:
- `m_script_database.txt` - Your question database
- `users.json` - User credentials (provided in private-repo folder)

### Step 2: Create GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name: `Quiz App Token`
4. Select scope: **`repo`** (Full control of private repositories)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)

### Step 3: Deploy to Render

1. Sign up at [render.com](https://render.com) (use GitHub login)
2. Click "New +" → "Web Service"
3. Connect this public repository
4. Configure:
   - **Name**: `matlab-quiz` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: `Free`

5. Add Environment Variables:
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `PRIVATE_REPO`: Your private repo in format `username/repo-name`
   - `RESULTS_DIR`: `/opt/render/project/.data` (for persistent storage)

6. Click "Create Web Service"

### Step 4: Enable Persistent Disk (for results storage)

1. In your Render service dashboard
2. Go to "Disks" tab
3. Click "Add Disk"
4. Name: `results-storage`
5. Mount Path: `/opt/render/project/.data`
6. Size: 1 GB (free)
7. Save

### Step 5: Test the Application

1. Render will provide a URL: `https://your-service-name.onrender.com`
2. Open the URL
3. Login with sample credentials:
   - Username: `admin`, Password: `admin123`
   - Username: `john`, Password: `john123`

## Usage

### For Students/Users

1. Navigate to the quiz URL
2. Login with your credentials
3. Take the 30-question quiz within 30 minutes
4. Submit or wait for auto-submit
5. View your results and correct answers

### For Administrators

#### Adding New Users

Edit `users.json` in private repo:

```python
# Generate password hash
import bcrypt
password = "newpassword123"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

Add to `users.json`:
```json
{
  "username": "newuser",
  "password": "hash-generated-above",
  "comment": "Password: newpassword123"
}
```

#### Updating Questions

Simply edit `m_script_database.txt` in private repo. Changes take effect immediately.

#### Viewing Results

1. Login to Render dashboard
2. Go to your service → "Disk" tab
3. Browse to `/opt/render/project/.data/results.json`
4. Download and view in text editor or Excel

## File Structure

```
public-repo/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/
│   ├── login.html        # Login page
│   └── quiz.html         # Quiz interface
├── static/
│   ├── style.css         # Styling
│   └── quiz.js           # Quiz logic
└── README.md             # This file

private-repo/
├── m_script_database.txt # Question database (1500 questions)
├── users.json            # User credentials
└── README.md             # Setup instructions
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | `abc123...` |
| `GITHUB_TOKEN` | GitHub PAT with repo access | `ghp_xxx...` |
| `PRIVATE_REPO` | Private repo name | `username/quiz-db` |
| `RESULTS_DIR` | Results storage path | `/opt/render/project/.data` |

## Troubleshooting

### Cold Starts
Free tier spins down after 15 min inactivity. First load may take 30-60s. The app includes keep-alive pings to minimize this.

### Authentication Issues
- Verify `GITHUB_TOKEN` is correct and has `repo` scope
- Check `PRIVATE_REPO` format: `username/repo-name`
- Ensure private repo exists and contains required files

### Questions Not Loading
- Check private repo file name: `m_script_database.txt`
- Verify GitHub token has access to private repo
- Check Render logs for errors

### Results Not Saving
- Ensure persistent disk is created and mounted
- Check `RESULTS_DIR` matches mount path
- Verify disk has available space

## Support

For issues or questions:
1. Check Render logs: Dashboard → Logs tab
2. Verify environment variables are set correctly
3. Test GitHub API access manually

## License

This application is for educational purposes. Question database remains private.

## Credits

Developed for MATLAB/Simulink M-Scripting training and assessment.
