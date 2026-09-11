# DataKite AI — Deploy Now

## Recommended production launch

This package is ready for a Docker-based deployment platform.

1. Create a new Web Service from this project/repository.
2. Use the included `Dockerfile`.
3. Set the service port to `8000` if the platform asks for one.
4. Set `FLASK_DEBUG=0`.
5. Optional: set `MAX_UPLOAD_MB`, `MAX_PDF_PAGES`, `UPLOAD_MAX_AGE_HOURS`, and `CLEANUP_INTERVAL_MINUTES`.
6. After deployment, open the public HTTPS URL.
7. Verify `/health` returns a healthy response.
8. Test upload → dashboard → Ask DataKite → exports on both laptop and phone.

## Important production note

The default upload storage is local disk and is cleaned automatically. For a multi-instance deployment, move persistent files/session state to object storage/database before scaling horizontally.
