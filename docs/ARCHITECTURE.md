# Architecture

Frontend: `index.html`, `style.css`, `script.js`.

Backend: Flask API plus modular analytics engines. `smart_analytics_engine.py` is the natural-language orchestration layer and runs against the current uploaded DataFrame.

Supported analysis: KPI, category/region/city/product ranking, monthly trend/growth, root cause, anomalies, forecasting, comparison, customer concentration, insights and recommendations.

Universal upload normalizes supported tabular inputs into `uploads/current_data.csv`. Multiple files are union-concatenated with `__source_file` so year/file comparisons remain possible without fixed filenames.
