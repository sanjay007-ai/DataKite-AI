# DataKite AI — UX, Help & Error Safety Upgrade

This release adds a user-facing reliability layer designed to keep technical backend errors out of the normal product experience.

## What users see
- **Help** button in the workspace.
- First-time **4-step guide**: Upload → Understand → Analyze → Ask & decide.
- Contextual help topics for upload, AI questions, dashboard, exports, errors and installation.
- Friendly error cards using: **Problem → Simple explanation → Fix → Try again**.
- Automatic temporary error dismissal after 12 seconds.
- Retry action for upload, AI question, dashboard and exports when retrying is safe.
- File/upload notices when some files were skipped or only partially usable.
- Loading messages such as “Reading your data…” and “Analyzing your data…”.
- Install guidance when Chrome's PWA install prompt is available.

## What users should NOT see
- Python tracebacks.
- Flask/internal server paths.
- SQLite/database paths.
- Raw exception details in normal UI.
- Internal implementation terminology.

## End-user flow
1. User signs in.
2. User sees the four-step guide on first workspace entry.
3. User uploads one or more files.
4. DataKite reports success, partial success, or a friendly error.
5. User can open **? Help** at any time.
6. If an action fails, the user gets a simple explanation and **Try again** where appropriate.
7. Technical debugging remains a developer/log concern, not a customer-facing message.

## Installation
On supported browsers, DataKite can be installed as a PWA. The workspace exposes an **Install app** button when the browser supplies the install prompt; otherwise Help explains the browser's install/Add to Home Screen option.

## Production note
The current Vercel test architecture uses `/tmp` for SQLite and uploaded files. That storage is ephemeral. Before calling the system final production, move account data to a persistent database and uploaded/generated files to persistent object storage or use a persistent application host.
