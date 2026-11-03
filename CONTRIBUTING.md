# Contributing

## Development setup

Use the repository virtual environment for Python commands:

```text
C:\Projects\closedai\.venv\Scripts\python.exe
```

Install backend dependencies and run the tests:

```bash
cd backend
C:\Projects\closedai\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
C:\Projects\closedai\.venv\Scripts\python.exe -m pytest
C:\Projects\closedai\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Install and run the frontend:

```bash
cd frontend
npm ci
npm test
npm run build
npm run dev
```

## Pull requests

- Keep changes focused and preserve existing behavior.
- Add or update tests for behavior changes.
- Do not commit secrets, real personal data, production URLs, or local environment files.
- Run relevant backend and frontend checks before submitting.
- Database changes require an Alembic migration when operators need schema updates.

## Documentation

Keep README setup instructions aligned with `.env.example`, `docker-compose.yml`, and supported application settings.
