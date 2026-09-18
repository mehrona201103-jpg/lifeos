# LIFEOS

**Personal Life Operating System** — habits, tasks, goals, finance and statistics in one modern web app.

Built with **FastAPI**, **SQLAlchemy**, **Jinja2** and vanilla HTML/CSS/JS. Designed for easy deployment on **Railway**.

---

## Features (planned / in progress)

- User registration & authentication (session-based)
- Habits with streak tracking
- Task manager (priorities, filters, recurring)
- Goals with progress
- Personal finance (income / expense, multi-currency)
- Calendar & statistics with real charts
- Profile, settings, theme (dark/light), localization
- Full Admin Panel (users, content, social links, logs, backups)
- Instagram & TikTok links managed from admin

---

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Backend      | Python 3.11, FastAPI, Uvicorn       |
| ORM          | SQLAlchemy 2 + Alembic              |
| Database     | PostgreSQL (prod) / SQLite (local)  |
| Frontend     | HTML5, CSS3, JavaScript, Chart.js   |
| Auth         | Argon2id / bcrypt, secure sessions  |
| Deploy       | Railway + Docker                    |

---

## Quick Start (Local)

### 1. Requirements

- Python 3.11 64-bit
- Git

### 2. Clone & setup

```bash
git clone <your-repo-url>
cd LIFEOS

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY and ADMIN_PASSWORD
```

### 4. Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000

Health check: http://localhost:8000/health

---

## Railway Deployment

### Required Variables (Railway → Variables)

| Variable          | Description                              | Example / Note                     |
|-------------------|------------------------------------------|------------------------------------|
| `DATABASE_URL`    | PostgreSQL connection string             | Provided by Railway PostgreSQL     |
| `SECRET_KEY`      | Long random secret                       | Generate with `openssl rand -hex 32` |
| `ADMIN_PASSWORD`  | Strong password for first admin login    | **Never commit this**              |
| `ENVIRONMENT`     | `production`                             |                                    |
| `APP_NAME`        | Optional, defaults to LIFEOS             |                                    |
| `ALLOWED_ORIGINS` | Your domain or `*`                       | https://your-app.up.railway.app    |

### Steps

1. Create a new project on Railway
2. Add **PostgreSQL** plugin → copy `DATABASE_URL`
3. Connect your GitHub repository
4. Set the variables above
5. Deploy (Railway will use the `Dockerfile`)
6. Check `/health` endpoint
7. Open the public URL and register the first user
8. Use the hidden admin access (see Admin section) with `ADMIN_PASSWORD`

### Start command (already in Dockerfile)

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Project Structure

```
LIFEOS/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings from env
│   ├── database/
│   │   ├── connection.py
│   │   └── models.py        # (later stages)
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   ├── security/
│   ├── templates/
│   └── static/
├── tests/
├── requirements.txt
├── Dockerfile
├── railway.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## Development Roadmap

- [x] **Stage 1** — Project structure, config, Dockerfile, requirements
- [ ] **Stage 2** — Database models & migrations
- [ ] **Stage 3** — Auth (register / login / logout / roles)
- [ ] **Stage 4** — Dashboard & core UI
- [ ] **Stage 5** — Habits, Tasks, Goals
- [ ] **Stage 6** — Finance, Calendar, Statistics
- [ ] **Stage 7** — Profile & Settings
- [ ] **Stage 8** — Full Admin Panel
- [ ] **Stage 9** — Social links management
- [ ] **Stage 10** — Railway polish & docs
- [ ] **Stage 11** — Tests & final checks

---

## Security Notes

- Passwords are hashed (Argon2id / bcrypt) — never stored in plain text
- `ADMIN_PASSWORD` and `SECRET_KEY` must be set via environment variables
- No secrets in source code or Git
- Admin routes are protected by role checks on the server
- Rate limiting on login attempts (implemented in later stages)

---

## License

Private project. All rights reserved.
