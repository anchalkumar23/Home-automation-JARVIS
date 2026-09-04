# JARVIS Backend

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## API Keys

The backend runs in local fallback mode without keys. Add one of these to `backend/.env` for real model routing:

```env
JARVIS_PROVIDER=auto
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-5.4-mini
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-8b-instant
```
