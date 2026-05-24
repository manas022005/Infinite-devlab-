# Infinite DevLab

AI-powered coding lab with CSS Lab, CodeBreaker, DSA Visualizer and Problem
Solver modules. Python (Flask) backend, MySQL database, vanilla-JS frontend.

## Stack

- **Backend:** Flask 3, SQLAlchemy, PyJWT, bcrypt, gunicorn
- **Database:** MySQL 8 (works with SQLite for quick local trial)
- **Frontend:** Static HTML/CSS/JS (Inter font, dark theme #070b14 / accent #3b82f6 / gold #fbbf24)
- **Deploy:** Single Docker container (frontend served by Flask)

## Project layout

```
infinite-devlab/
├── backend/
│   ├── app.py            # Flask app (auth + api + static serving)
│   ├── requirements.txt
│   ├── schema.sql        # MySQL schema (auto-loaded by docker-compose)
│   └── .env.example
├── frontend/
│   ├── index.html        # Landing + SPA shell (avatar dropdown when signed in)
│   ├── login.html        # Sign in / Sign up (theme-matched, tabs + swap link)
│   ├── config.js         # API base URL (same-origin by default)
│   ├── module1.html      # CSS Quest
│   ├── module2.html      # CodeBreaker
│   ├── module 4.html     # Problem Solver
│   └── dsa vizualizer/   # DSA module
├── Dockerfile
├── docker-compose.yml
└── render.yaml
```

## What was fixed vs the original frontend

- Login/signup page restyled to match the main dark-blue theme (no more
  purple Indigo mismatch) and given proper tab styles.
- `index.html` now shows a circular **avatar with a dropdown** (Dashboard,
  History, Sign out) once you're logged in, instead of dangling Login/Register
  buttons. Token & user are kept in `localStorage` and re-validated via
  `/auth/me` on load.
- Module paths corrected to the actual filenames in the zip
  (`module1.html`, `module2.html`, `module 4.html`, `dsa vizualizer/index.html`).
- Dashboard and History nav links now open real inline panels that hit the API.
- Inter font kept everywhere for consistency.

## Run locally with Docker (recommended)

```bash
docker compose up --build
# open http://localhost:8000
```

MySQL is created automatically and seeded with `backend/schema.sql`.

## Run locally without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# For a 60-second trial set DATABASE_URL=sqlite:///devlab.db
python app.py
# open http://localhost:8000
```

## Deploy

The repo is a single Docker image — point any container host at the Dockerfile.

### Render (one click via render.yaml)

1. Push this repo to GitHub.
2. In Render → New → Blueprint → connect repo. It reads `render.yaml`.
3. Provision MySQL anywhere (Railway, Aiven, PlanetScale, AWS RDS, …) and paste
   the connection string into the `DATABASE_URL` env var.
4. Deploy. The container exposes port 8000 and serves both the API and the
   frontend on the same origin.

### Railway / Fly.io / Cloud Run / Heroku

Any platform that builds from a `Dockerfile` works. Set these env vars:

| Variable          | Example                                                  |
|-------------------|----------------------------------------------------------|
| `DATABASE_URL`    | `mysql+pymysql://user:pass@host:3306/devlab`             |
| `JWT_SECRET`      | a long random string                                     |
| `JWT_EXPIRES_HOURS` | `24`                                                   |
| `CORS_ORIGINS`    | `*` or your domain                                       |
| `FRONTEND_DIR`    | `/app/frontend` (already set in the image)               |

## API

| Method | Path             | Description                                  |
|--------|------------------|----------------------------------------------|
| POST   | `/auth/signup`   | `{name,email,password}` → user JSON          |
| POST   | `/auth/login`    | form `username,password` → `access_token`    |
| GET    | `/auth/me`       | bearer token → current user                  |
| GET    | `/api/progress`  | list per-module progress                     |
| POST   | `/api/progress`  | `{module,level,score}` upsert (keeps max)    |
| GET    | `/api/history`   | last 100 activity entries                    |
| POST   | `/api/history`   | `{action,detail}`                            |
| GET    | `/api/health`    | liveness probe                               |

All `/api/*` and `/auth/me` require `Authorization: Bearer <token>`.

## Notes

- Passwords are bcrypt-hashed; tokens are HS256 JWT.
- The avatar shows the first letter of the user's name — no upload required.
- If you change MySQL credentials, also update `docker-compose.yml`.
