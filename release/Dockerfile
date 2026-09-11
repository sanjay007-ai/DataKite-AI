# Data Analyst AI Assistant — production image
#
# Includes LibreOffice, required by the /convert/* document
# conversion routes (they shell out to `soffice --headless`).
# This makes the image large (~600MB+) — that's expected.

FROM python:3.12-slim

# System dependencies: LibreOffice for document conversion,
# fontconfig + common fonts so generated/converted documents render
# text correctly.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-dejavu \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

# uploads/ is created automatically by app.py on startup, but
# creating it here means it exists (and is owned correctly) even
# before the first request.
RUN mkdir -p uploads

ENV PORT=8000
ENV FLASK_DEBUG=0
EXPOSE 8000

WORKDIR /app/backend

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "app:app"]
