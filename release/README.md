# DataKite AI — Final

Universal business-data analyst for Excel, CSV, JSON, PDF tables, Word tables and PowerPoint content.

## Core flow
Upload 1–10 business files → dataset intelligence → natural-language questions → KPI/chart/table/trend/root-cause/comparison/forecast/insight/recommendation → export.

## Supported outputs
- Premium Excel dashboard (`/excel/download`)
- PDF/Word/PowerPoint reports where supported by the existing routes
- Chart ZIP (`/charts/download`)
- Filter/current data CSV (`/data/download`)



## Local start
Run `START_HERE_Windows.bat` on Windows, then open `http://127.0.0.1:5000`.

## Production
`Procfile` uses Gunicorn. Set `PORT`, `MAX_UPLOAD_MB`, `MAX_PDF_PAGES`, and cleanup environment variables as needed.

## No fixed company/year dataset
Analytics operate on the currently uploaded data. No DMart/2024/2025 files are required for ordinary questions.


## Performance
The production build lazy-loads heavy document/report/export libraries so normal uploads and dashboard requests do not pay the full PowerPoint/Word/PDF/Excel import cost at cold start. Dashboard requests also prevent duplicate concurrent bootstrap calls.
