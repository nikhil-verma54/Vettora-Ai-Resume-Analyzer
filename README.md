# Vettora — AI-Powered Resume Analyzer & Voice Mock Interviewer

> **Land more interviews. Nail every round. Vettora uses AI to optimize your resume for ATS systems and prepare you with realistic voice mock interviews.**

![Status](https://img.shields.io/badge/status-live-brightgreen?style=for-the-badge)
![Backend](https://img.shields.io/badge/backend-Render%20%2B%20PostgreSQL-46E3B7?style=for-the-badge&logo=render)
![Frontend](https://img.shields.io/badge/frontend-Vercel-black?style=for-the-badge&logo=vercel)
![Auth](https://img.shields.io/badge/auth-Firebase-FFCA28?style=for-the-badge&logo=firebase)

---

## 🌐 Live App

| Service | URL |
|---|---|
| 🖥️ **Frontend** | [vettora-resume-analyzer.vercel.app](https://vettora-resume-analyzer.vercel.app) |
| ⚙️ **Backend API** | [hackinmotion-ricr-him-1236.onrender.com](https://hackinmotion-ricr-him-1236.onrender.com) |

> **Note**: The backend is on Render's free tier and may take **30–60 seconds to wake up** after a period of inactivity.

---

## 📌 What is Vettora?

**Vettora** is a career readiness platform built to solve a real problem: over **75% of resumes are filtered out before a human recruiter ever sees them**, due to non-standard formatting, missing keywords, or vague bullet points.

Vettora gives candidates the tools to fight back:

1. **AI Resume Auditor** — Deep ATS scoring, section analysis, and job description keyword matching powered by Google Gemini.
2. **Voice Mock Interviewer** — Realistic AI-generated interview sessions based on your actual resume, with speech-to-text answers and instant AI feedback.

---

## ✨ Features

### 📄 Smart Resume Evaluation
- **ATS Compatibility Check** — Detects formatting issues, extractability, and section structure
- **10-dimension Scoring** — Rates your resume across skills quality, experience, projects, achievements, writing clarity, technical depth, and more
- **Job Description Matcher** — Compares your resume to any job posting and identifies matched, partial, and missing skills
- **Actionable Suggestions** — Specific, prioritized improvements with strong action verb recommendations

### 🎙️ AI Voice Mock Interviewer
- **Personalized Questions** — 10 questions (7 technical + 3 behavioral) generated from your actual resume and target role
- **Text-to-Speech** — The AI interviewer reads each question aloud with animated voice waves
- **Speech-to-Text** — Dictate your answers in real-time using live voice recognition
- **Per-answer Feedback** — Scored on Clarity, Relevance, and Completeness with actionable improvement tips
- **Session Summary** — Overall rating out of 10, verdict, key strengths, and growth areas

### 📊 Dashboard & History
- **Stats Overview** — Highest and lowest resume scores across all your scans
- **Resume History** — View, re-open, or delete any past analysis report
- **Interview History** — Review past mock interview sessions, scores, and full question-by-question breakdowns

---

## 🛠️ Tech Stack

**Tech Stack:** React 19, Django REST Framework, PostgreSQL, Google Gemini API, OpenAI API, Firebase Auth, Tailwind CSS v4, Vite 8, Vercel, Render

### Frontend
- **React 19** + **Vite 8** — UI and build tooling
- **React Router v7** — Client-side routing
- **Tailwind CSS v4** — Utility-first styling
- **Firebase JS SDK** — Google OAuth + Email/Password authentication
- **Web Speech API** — `SpeechSynthesis` (TTS) + `webkitSpeechRecognition` (STT)

### Backend
- **Django 5** + **Django REST Framework** — API layer
- **Google Gemini API** (`gemini-flash-latest`) — Resume analysis and question generation
- **PyMuPDF** + **python-docx** — PDF and DOCX resume parsing
- **Firebase Admin SDK** — Server-side JWT token verification
- **Pydantic v2** — AI response schema validation and type safety
- **Gunicorn** + **WhiteNoise** — Production WSGI server and static files

### Database & Deployment
- **PostgreSQL** (Render managed) — Production database
- **SQLite** — Local development database
- **Vercel** — Frontend hosting and CDN
- **Render** — Backend hosting

### Database Models
| Model | Description |
|---|---|
| `UserProfile` | Linked to Firebase UID — stores display name, email, and timestamps |
| `ResumeAnalysis` | Stores resume text, overall score, section breakdown, and full analysis JSON |
| `MockInterview` | Stores interview sessions, target role, overall rating, and performance summary |
| `InterviewQuestion` | Stores each question, user answer, AI score, and per-dimension feedback |

---

## 🔄 Application Flow

```
[Sign Up / Log In via Firebase]
       |
       +--> [Dashboard]
       |       +--> Upload Resume (.pdf / .docx)
       |       +--> Paste Job Description
       |       +--> Get AI Analysis: ATS Score, Skill Gaps, Improvement Tips
       |       +--> View / Delete Past Scan History
       |
       +--> [Mock Interview]
               +--> Choose Target Role + Upload Resume
               +--> AI Generates 10 Custom Questions
               +--> Voice Interaction (AI speaks, you answer by voice)
               +--> Real-time Per-answer Feedback
               +--> Full Session Summary + History Review
```

---

## 🚀 Run Locally

### Prerequisites
- **Node.js** v18+ and **npm**
- **Python** v3.10+ and **pip**
- A **Google Gemini API Key** from [aistudio.google.com](https://aistudio.google.com/)
- A **Firebase Project** for authentication

### 1. Clone
```bash
git clone https://github.com/nikhil-verma54/HackInMotion-RICR-HIM-1236.git
cd HackInMotion-RICR-HIM-1236
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env`:
```env
DJANGO_SECRET_KEY=your_django_secret_key
DJANGO_DEBUG=True
GEMINI_API_KEY=your_google_gemini_api_key
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:5173
```

```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```env
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
VITE_FIREBASE_APP_ID=your_app_id
VITE_API_URL=http://127.0.0.1:8000
```

```bash
npm run dev
```

App runs at `http://localhost:5173`

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/login/` | `POST` | Verify Firebase token and sync user profile |
| `/api/auth/logout/` | `POST` | Clear Django session |
| `/api/resume/upload/` | `POST` | Upload and extract resume text |
| `/api/resume/analyze/` | `POST` | Analyze resume against a job description |
| `/api/resume/dashboard/` | `GET` | User stats and past analysis history |
| `/api/resume/history/<id>/` | `GET` / `DELETE` | View or delete a past scan |
| `/api/resume/interview/start/` | `POST` | Generate questions and start interview session |
| `/api/resume/interview/<id>/answer/` | `POST` | Submit and evaluate an answer |
| `/api/resume/interview/<id>/finish/` | `POST` | Finalize session and generate summary |
| `/api/resume/interview/history/` | `GET` | List past mock interview sessions |
| `/api/resume/interview/<id>/detail/` | `GET` | Full interview review with all Q&A and feedback |

---

## 🏁 Deployment Status

| Component | Status | Platform |
|---|---|---|
| 🖥️ Frontend | ✅ Live | Vercel |
| ⚙️ Backend API | ✅ Live | Render |
| 🗄️ Database | ✅ PostgreSQL | Render |
| 🔐 Authentication | ✅ Active | Firebase Auth |
| 🤖 AI Engine | ✅ Connected | Google Gemini API |

---

## 📄 License

Built and maintained by [Nikhil Verma](https://github.com/nikhil-verma54). Feel free to open issues or submit pull requests!
