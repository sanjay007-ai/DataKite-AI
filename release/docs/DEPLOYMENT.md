# Deployment

1. Install Python and dependencies from `backend/requirements.txt`.
2. Local Windows: run `START_HERE_Windows.bat`.
3. Production: use the supplied `Procfile` with Gunicorn.
4. Never enable `FLASK_DEBUG=1` in production.
5. Configure upload limits and cleanup settings with environment variables.
