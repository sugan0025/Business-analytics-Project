<div align="center">

  <img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/header-banner.svg" alt="Faculty Guide Selection Banner" width="100%" />

  <br/><br/>

  <a href="https://readme-typing-svg.demolab.com">
    <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=16&pause=1000&color=38BDF8&center=true&vCenter=true&width=700&lines=High-Concurrency+FCFS+Faculty+Guide+Selection+Platform;Zero+Race+Conditions+%E2%80%A2+PostgreSQL+Row-Level+Locks;Instant+Sub-250ms+Auth+Latency+%E2%80%A2+Zero+Waterfall+Loading;Automated+Google+Sheets+API+v4+Idempotent+Sync" alt="Typing SVG" />
  </a>

  <br/><br/>

  [![Vercel Deployment](https://img.shields.io/badge/Deployment-Vercel%20Serverless-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://faculty-selection-bitsathy.vercel.app)
  [![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Flask](https://img.shields.io/badge/Backend-Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
  [![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20(Neon)-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech)
  [![Google Sheets API](https://img.shields.io/badge/Sync-Google%20Sheets%20v4-34A853?style=for-the-badge&logo=googlesheets&logoColor=white)](https://developers.google.com/sheets/api)
  [![Google OAuth](https://img.shields.io/badge/Auth-Google%20Identity%20OAuth-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/identity)
  [![Tests](https://img.shields.io/badge/Tests-43%20Passing-10B981?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)

  <br/>

  <p align="center">
    <b>🌐 Live Production URL:</b> <a href="https://faculty-selection-bitsathy.vercel.app"><b>https://faculty-selection-bitsathy.vercel.app</b></a>
  </p>

</div>

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🏛️ System Architecture & Workflow

<div align="center">
  <img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/architecture-diagram.svg" alt="System Architecture Diagram" width="100%" />
</div>

<br/>

A high-concurrency, Google-Form-style web application where MBA students pick one faculty member, strictly first-come first-served.
- **10 Faculty Members, 44 Students** (default seat quotas: 5, 5, 5, 5, 4, 4, 4, 4, 4, 4).
- **Authentication**: Students sign in with their `@bitsathy.ac.in` Google account.
- **Fair Play Window**: 60 seconds per student to review and submit their selection.
- **Real-Time Mirroring**: Every confirmed response writes immediately to Google Sheets.
- **Zero Race Conditions**: Seats are claimed via atomic PostgreSQL queries (`UPDATE faculty SET selected_count = selected_count + 1 WHERE selected_count < capacity`) and database-level `CHECK` constraints. Two students can never acquire the same last seat.
- **Live Seat Availability**: Faculty cards grey out ("Full") the instant capacity is reached; seat counters refresh every 3 seconds for active users.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 1. Before the Real Run: Fill in `roster.csv`

Add each student's college email in the `email` column (`name.mb25@bitsathy.ac.in`):
```csv
register_number,name,email
7376257MB101,John Doe,johndoe.mb25@bitsathy.ac.in
```
- Once emails are populated, the app operates in **Strict Identity Mode**: a student can only sign in with an email present in the roster, permanently bound to their registered roll number.
- Seat counts live in `faculty.csv`. The app loads both files dynamically.
- The institutional domain defaults to `bitsathy.ac.in`. If needed, override with `ALLOWED_EMAIL_DOMAIN`.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 2. Google Cloud Setup (One-Time)

1. Open [Google Cloud Console](https://console.cloud.google.com) and create or select your project.
2. **Google OAuth 2.0 Client**:
   - Go to **APIs & Services** > **OAuth consent screen** (choose *Internal* for Google Workspace, or *External*).
   - Under **Credentials** > **Create Credentials** > **OAuth client ID**, choose **Web application**.
   - Under **Authorized JavaScript origins**, add:
     - `https://faculty-selection-bitsathy.vercel.app`
     - `http://localhost:5000`
   - Copy the Client ID into `GOOGLE_CLIENT_ID`.
3. **Google Sheets Service Account**:
   - Enable the **Google Sheets API**.
   - Navigate to **IAM & Admin** > **Service accounts** > **Create service account**.
   - Go to **Keys** > **Add key** > **Create new key** (JSON). Copy the full JSON content into `GOOGLE_SERVICE_ACCOUNT_JSON`.
   - Open your Google Sheet, click **Share**, and grant the service account email **Editor** access.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 3. Deploying to Vercel (Production)

1. Connect the GitHub repository to [Vercel](https://vercel.com).
2. Under **Storage**, create a **Neon PostgreSQL** database and link it to the project. This sets `DATABASE_URL` automatically.
3. Under **Settings > Environment Variables**, configure:

   | Name | Value |
   |---|---|
   | `SECRET_KEY` | High-entropy random secret key |
   | `GOOGLE_CLIENT_ID` | OAuth Client ID from step 2 |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON credentials string |
   | `GOOGLE_SHEET_ID` | `1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI` |
   | `OPEN_AT` | *(Optional)* e.g. `2026-10-07T10:00:00+05:30` to enforce synchronized start |
   | `SYNC_TOKEN` | *(Optional)* Secret token for triggering manual sync |

4. Redeploy. Verify health via `https://faculty-selection-bitsathy.vercel.app/healthz`. Both `"ok": true` and `"sheets_configured": true` should be returned.
5. Initialize sheet tabs from your terminal: `python manage.py init-sheet`.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 4. Organiser CLI Commands (`manage.py`)

Run administrative management commands directly:

```bash
# Set up virtual environment
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Inspect current seat allocation status
python manage.py status

# List every selection in strict millisecond FCFS order
python manage.py list

# Free a student's seat (clears DB record & clears Google Sheet row)
python manage.py reset 7376257MB101

# Re-push any pending/buffered rows to Google Sheets
python manage.py sync

# Initialize Google Sheet tabs (Responses + Summary)
python manage.py init-sheet

# Create a local CSV backup
python manage.py export export.csv
```

> **Resilient Sync Guarantee**: If Google Sheets is temporarily unreachable, student seat claims remain 100% safe in PostgreSQL. Responses are queued and re-pushed upon the next submission or via `python manage.py sync`. Because row numbers are calculated deterministically (`row = response_number + 1`), retries can never produce duplicates.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 5. Local Development & Testing

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run full 43-test suite (capacity, duplicates, timer, auth, concurrency, sheets)
python -m pytest

# Create .env from template with DEV_LOGIN enabled
cp .env.example .env

# Run local development server
python -m flask --app app run -p 5000
```

Open `http://localhost:5000`. Without `DATABASE_URL`, the application automatically provisions and utilizes a local SQLite database (`faculty.db`).

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 6. How Fairness Guarantees Work

| Invariant | Enforcement Mechanism |
|---|---|
| **Capacity Never Exceeded** | `UPDATE faculty SET selected_count = selected_count + 1 WHERE selected_count < capacity` + DB `CHECK` constraint |
| **Race Conditions Eliminated** | PostgreSQL transaction row locking (`SELECT FOR UPDATE`) serializes simultaneous claims |
| **Single Response Per Student** | Unique constraint on email and register number; repeat requests return original confirmation |
| **Impersonation Prevention** | Verified Google Identity JWT bound directly to authorized `roster.csv` roll number |
| **60-Second Selection Timer** | Server records session start timestamp and rejects late submits (2s network jitter grace) |
| **Transaction Integrity** | Zero data written to Google Sheets or permanent state until atomic DB claim succeeds |
