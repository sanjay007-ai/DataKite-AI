# DataKite AI Analyst V2

## What changed
DataKite now uses a deterministic-first analyst path for ordinary business questions.

**Question → Intent → Calculation → Validation → Evidence → Smart chart → Explanation → Recommendations → Follow-ups → Memory**

### Core guarantees
- Numeric answers are calculated from the loaded pandas dataset before any narrative model is used.
- Results are validated for finite numeric values before being returned.
- Responses include evidence cards when evidence is available.
- Trend, comparison, product/category/geo, anomaly and forecast questions can produce an inline smart chart.
- Recommendations and suggested next questions are returned with the analysis.
- The last 8 compact analyst interactions are stored in the signed user session and used for short follow-up questions.
- Uploading a new dataset clears the analyst conversation context.

### Important architecture note
The current V2 path intentionally does **not** let the LLM invent or calculate business numbers. A future narrative-model pass can consume the verified calculation object and only improve wording.
