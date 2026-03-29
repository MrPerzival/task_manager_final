# Task Manager — Full Stack App
> Flutter + FastAPI + SQLite / PostgreSQL | Production-Ready

---

## Quick start

### Backend — SQLite (zero config, local dev)

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# API:  http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

### Backend — PostgreSQL (Docker)

```bash
cd backend
docker compose up --build
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Flutter

```bash
cd flutter_app
flutter pub get
flutter run
```

> **Set your backend URL** in `lib/services/api_service.dart` → `ApiConfig.baseUrl`
> - iOS simulator / desktop: `http://127.0.0.1:8000`
> - Android emulator: `http://10.0.2.2:8000`
> - Physical device: `http://<your-lan-ip>:8000`
> - Production: `https://task-manager-api.onrender.com`

---

## Project structure

```
task-manager/               ← GitHub repo root
├── render.yaml             ← Render.com Blueprint (DB + API)
├── .github/
│   └── workflows/
│       └── ci.yml          ← GitHub Actions CI
│
├── backend/
│   ├── main.py             ← FastAPI app + all routes
│   ├── database.py         ← SQLAlchemy engine (SQLite ↔ PostgreSQL)
│   ├── models.py           ← ORM Task model
│   ├── schemas.py          ← Pydantic schemas
│   ├── requirements.txt
│   ├── .python-version     ← Pins Python 3.11 for Render
│   ├── .env.example
│   ├── Makefile
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_create_tasks_table.py
│   │       └── 002_add_indexes.py
│   └── tests/
│       ├── conftest.py
│       ├── test_crud.py
│       ├── test_dependencies.py
│       ├── test_recurring.py
│       └── test_error_handling.py
│
└── flutter_app/
    ├── pubspec.yaml
    └── lib/
        ├── main.dart
        ├── models/task.dart
        ├── services/
        │   ├── api_service.dart
        │   ├── draft_service.dart
        │   └── task_provider.dart
        ├── screens/
        │   ├── task_list_screen.dart
        │   └── task_form_screen.dart
        └── widgets/
            ├── app_theme.dart
            ├── task_card.dart
            ├── connection_banner.dart
            └── empty_state.dart
```

---

## Data model

| Field | Type | Notes |
|---|---|---|
| id | int | Auto-generated |
| title | String(255) | Required, trimmed |
| description | String(2000) | Optional |
| due_date | Date | Optional |
| status | Enum | To-Do / In Progress / Done |
| blocked_by | int? | ID of blocking task |
| recurring | Enum | None / Daily / Weekly |

---

## API reference

| Method | Path | Description |
|---|---|---|
| GET | / | Health check |
| GET | /tasks | List tasks (filter by status, search) |
| POST | /tasks | Create task (+2s async delay) |
| PUT | /tasks/{id} | Update task (+2s async delay) |
| DELETE | /tasks/{id} | Delete + clear orphan blocked_by refs |

**All error responses:** `{ "error": true, "detail": "..." }`

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./tasks.db` | SQLAlchemy connection string |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `PORT` | `8000` | Uvicorn bind port (Render uses 10000) |

---

## Key features explained

### Async handling
`asyncio.sleep(2)` on POST/PUT yields the event loop — the server stays
responsive while Flutter shows a spinner and disables the Save button.

### Recurring task spawn
When status transitions to `Done` and `recurring != None`:
- **Daily** → new task with `due_date + 1 day`, `status = To-Do`
- **Weekly** → new task with `due_date + 7 days`, `status = To-Do`
- Idempotent: already-Done tasks do not spawn again

### Blocking / dependency
- `blocked_by` references another task's ID
- Flutter greys out and disables cards where the blocker is not Done
- Self-block → 422. Circular deps caught by DFS → 422
- Deleting a blocker clears `blocked_by` on all dependents

### Draft persistence
Every keystroke in the task form is saved to SharedPreferences.
Re-opening the form prompts to restore the draft.

---

## Deploying to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your repo — Render detects `render.yaml` at the root
4. Click **Apply** — provisions PostgreSQL + API automatically
5. After deploy, run migrations from the Render **Shell** tab:
   ```bash
   alembic upgrade head
   ```
6. Update `ApiConfig.baseUrl` in Flutter to your Render URL
7. Rebuild Flutter: `flutter build apk --release`

> **Note:** Free tier services spin down after 15 min of inactivity.
> First request after sleep takes 30–60s to wake up.
> Upgrade to Starter (~$7/mo) for always-on.

---

## Running tests

```bash
cd backend
pip install pytest pytest-asyncio httpx
DATABASE_URL="sqlite:///:memory:" pytest -v

# Or with the Makefile:
make install-dev
make test
```

---

## Makefile shortcuts

```bash
make dev              # hot-reload dev server
make test             # full test suite
make test-cov         # coverage report → htmlcov/index.html
make lint             # ruff linter
make format           # black formatter
make migrate          # apply all Alembic migrations
make migrate-create MSG="add priority field"
make docker-up        # PostgreSQL + API
make docker-down      # stop containers
make docker-clean     # stop + wipe DB volume
make clean            # remove __pycache__ etc.
```
