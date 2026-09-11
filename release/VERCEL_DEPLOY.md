# DataKite AI — Vercel test deployment

This build is adapted for a Vercel preview deployment. It uses /tmp for uploads and SQLite, so it is a demo/test deployment only; data and accounts are not durable across serverless instances/redeploys. For production, use a persistent database and object storage.

Required environment variables for real AI:
- GEMINI_API_KEY
- DATAKITE_SECRET_KEY
- GEMINI_MODEL=gemini-2.5-flash-lite
