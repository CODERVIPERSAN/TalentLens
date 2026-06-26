# TalentLens

TalentLens is an AI-powered talent intelligence platform that analyzes candidates beyond keywords, matching the right people to the right roles before traditional ATS scoring.

## Features

- **AI-Powered Matching**: Uses semantic embeddings and skill analysis to find the best candidate-job matches
- **Smart Skill Extraction**: Automatically extracts and analyzes skills from resumes using OpenAI
- **Deep Insights**: Get detailed match scores and analysis for better hiring decisions
- **Modern UI**: Clean, responsive React frontend with Tailwind CSS

## Tech Stack

### Backend
- FastAPI - Modern Python web framework
- SQLAlchemy - Async ORM for database operations
- SQLite (default) / PostgreSQL - Database
- OpenAI - Optional AI-powered analysis (falls back to a built-in local engine)

### Frontend
- React - UI library
- Vite - Build tool
- Tailwind CSS - Styling
- Lucide React - Icons

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+

The app runs out of the box on SQLite with no external services. PostgreSQL and
an OpenAI API key are both optional (see `.env.example`).

### Backend Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Defaults work as-is (SQLite, no OpenAI key). Edit only to customize.
```

3. Run the server (database tables are created automatically on startup):
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

## API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation.

## Project Structure

```
TalentLens/
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Configuration and security
│   ├── db/               # Database models and session
│   ├── schemas/          # Pydantic schemas
│   └── services/         # Business logic (AI, embeddings)
├── frontend/             # React frontend
├── alembic/              # Database migrations
└── requirements.txt      # Python dependencies
```

## License

See LICENSE file for details.
