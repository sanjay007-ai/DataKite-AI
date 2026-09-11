# Final QA / Changes

- Universal upload accepts one or multiple files (1–10).
- Excel/CSV/PDF-table/Word-table/PPT content is normalized where tabular data is available.
- Natural-language analytics uses the current uploaded dataset.
- Added robust date parsing and rejection of accidental 1970 epoch-only dates.
- Added natural best-vs-worst comparison.
- Added dynamic Excel dashboard generation without hard-coded Amount/Profit/Customer columns.
- Added data and chart exports.
- Added polished multi-format report exports and dark theme metadata.
- Windows launcher now resolves root/backend virtual environments reliably.
- Frontend script cache-busting added to avoid stale JavaScript.

## Upload Pipeline Fix — 2026-09-04
- Replaced fragile CSV delimiter sniffing with delimiter-aware raw parsing that tolerates title/blank rows.
- Excel ingestion is raw-first so report titles are not mistaken for headers.
- Added a shared `backend/upload_pipeline.py` used by the Flask `/upload` route and directly covered by regression tests.
- Preserved parsed DataFrames in memory; no Excel/Word/PPT/PDF second-pass CSV round trip.
- Added structured upload error codes and clearer per-file diagnostics.
- Bumped the PWA/service-worker cache and versioned `script.js` to prevent stale upload code after deployment.
- Fixed the legacy pytest helper being collected as a fixture; full test suite now passes.
