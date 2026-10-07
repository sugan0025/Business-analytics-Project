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
  [![License](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](LICENSE)

  <br/>

  <p align="center">
    <b>🌐 Live Production URL:</b> <a href="https://faculty-selection-bitsathy.vercel.app"><b>https://faculty-selection-bitsathy.vercel.app</b></a>
  </p>

</div>

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 📖 Executive Summary

The **Faculty Guide Selection Platform** is a mission-critical, high-concurrency web application designed for **Bannari Amman Institute of Technology (BIT Sathy)** II MBA students. During faculty guide selection, dozens of students attempt to select high-demand advisors in the exact same fraction of a second. Standard forms (like Google Forms or basic web apps) fail under this load due to race conditions, double-allocation of seats, out-of-order writes, and spreadsheet locking.

This system guarantees **strict First-Come, First-Served (FCFS) fairness**, **sub-250ms end-to-end response time**, **zero race conditions**, and **automatic, tamper-proof Google Sheets reconciliation**.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🏛️ System Architecture

<div align="center">
  <img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/architecture-diagram.svg" alt="System Architecture Diagram" width="100%" />
</div>

<br/>

### Core Architectural Pillars

1. **Client Layer (Mobile & Desktop Hardened)**:
   - Zero-waterfall preloaded state injection on initial page response.
   - 60-second selection countdown timer to prevent seat hoarding.
   - Dynamic 3-second seat availability polling with instant visual graying of filled faculty.
   - Full keyboard acceleration (`1-9` for immediate guide selection, `Enter` to confirm).
   - iOS Safari viewport hardening (`100dvh`, notch safe-areas, `-webkit-tap-highlight-color: transparent`).

2. **Edge & Authentication Gateway**:
   - Vercel Serverless Function entry point (`api/index.py`) running Python 3.12.
   - Google Identity Services (OAuth 2.0 JWT) verification.
   - Institutional domain lockdown (`@bitsathy.ac.in`).
   - High-speed in-memory Google RSA public key caching with auto-refresh on TTL expiry (reducing JWT validation latency from ~1,500ms to <50ms).
   - Strict identity-to-roster verification (students can only authenticate and submit for their own registered roll number).

3. **Atomic Concurrency Engine (Zero Race Conditions)**:
   - ACID-compliant transactional seat claiming powered by PostgreSQL (`Neon`).
   - Single-step atomic SQL updates with condition guards (`WHERE selected_count < capacity`) and database-level `CHECK` constraints.
   - High-throughput row-level locking (`SELECT FOR UPDATE`) guaranteeing that two simultaneous requests for the last available seat will serialize, allowing only the millisecond winner.
   - Idempotent request handling: Repeated submissions from the same student return the original confirmation without double-counting.

4. **Resilient Google Sheets Synchronization v4**:
   - Asynchronous background synchronization via Google Sheets API v4 using service account credentials.
   - Deterministic row allocation (`row_index = response_number + 1`) preventing duplicate or missing rows even under retry scenarios.
   - Automatic offline retry buffer: If the Google Sheets API experiences rate limits or timeouts, submissions remain safely committed in PostgreSQL and reconcile seamlessly.
   - Dual-tab synchronization: Writes detailed student audit logs to `Responses` and maintains live aggregated totals in `Summary`.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🌟 Key Features & Guarantees

| Guarantee | Technical Implementation | Impact |
|---|---|---|
| **Zero Oversubscription** | `UPDATE faculty SET selected_count = selected_count + 1 WHERE id = :id AND selected_count < capacity` + DB `CHECK (selected_count <= capacity)` | Impossible for any faculty to exceed seat quota |
| **Strict FCFS Millisecond Ordering** | PostgreSQL transaction serialization with timestamp ledger | Unambiguous first-come first-served ranking |
| **Tamper-Proof Identity** | Google Identity Services JWT cryptographically parsed on backend; student email matched against `roster.csv` | No impersonation; students cannot select on behalf of peers |
| **Sub-250ms Load Latency** | Preloaded state in initial HTML template + in-memory Google public key cache | No flash of unstyled content or multi-hop loading spinners |
| **60-Second Fair Play Timer** | Server-side start timestamp recording with 2-second network jitter tolerance | Prevents students from holding or locking slots indefinitely |
| **Offline Sheets Buffer** | Fallback queue in PostgreSQL with auto-retry and CLI reconciliation (`manage.py sync`) | Google Sheet hiccups never block student selections |

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 📂 Project Directory Structure

```
Business-analytics-Project/
├── assets/
│   ├── header-banner.svg          # High-fidelity SVG banner with metric badges
│   ├── architecture-diagram.svg   # 4-stage end-to-end architecture diagram
│   └── rainbow-divider.svg        # Modern animated gradient divider
└── faculty-form/
    ├── api/
    │   └── index.py               # Vercel serverless WSGI gateway
    ├── public/
    │   ├── form.js                # Form controller, 60s countdown, keyboard navigation
    │   └── styles.css             # Glassmorphic responsive styling, iOS safe area fixes
    ├── templates/
    │   └── index.html             # Preloaded server-rendered HTML template
    ├── tests/
    │   ├── conftest.py            # Pytest fixtures and mock Google services
    │   ├── test_allocation.py     # Concurrency, race condition, & capacity unit tests
    │   ├── test_auth.py           # JWT verification, domain check, & key cache tests
    │   └── test_sheets.py         # Google Sheets sync & retry buffer tests
    ├── allocation.py              # Atomic seat claiming & transaction logic
    ├── app.py                     # Flask application factory & REST endpoints
    ├── auth.py                    # Google Identity OAuth 2.0 & RSA certificate cache
    ├── config.py                  # Environment variable configuration loader
    ├── db.py                      # PostgreSQL connection pool & SQLite development fallback
    ├── faculty.csv                # Faculty list & maximum seat limits (10 guides, 44 seats)
    ├── roster.csv                 # Authorized student roster & email binding
    ├── manage.py                  # Administrative CLI (status, list, reset, sync, export)
    ├── sheets_sync.py             # Google Sheets API v4 reconciliation worker
    ├── requirements.txt           # Production dependencies for Vercel
    └── requirements-dev.txt       # Development & Pytest testing suite dependencies
```

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🚀 Quick Start & Local Setup

### 1. Clone & Environment Setup

```bash
# Clone the repository
git clone https://github.com/sugan0025/Business-analytics-Project.git
cd Business-analytics-Project/faculty-form

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt
```

### 2. Configure Environment Variables

Create a `.env` file inside `faculty-form/` based on `.env.example`:

```ini
# Core Flask Settings
SECRET_KEY=change-this-to-a-secure-random-key-in-production

# Authentication (Google Cloud Console OAuth 2.0 Client)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
ALLOWED_EMAIL_DOMAIN=bitsathy.ac.in

# Database (PostgreSQL for Neon/Supabase; leave empty for local SQLite)
DATABASE_URL=

# Google Sheets Integration
GOOGLE_SHEET_ID=1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI
GOOGLE_SERVICE_ACCOUNT_JSON=

# Selection Timing
SELECTION_WINDOW_SECONDS=60

# Offline Developer Mode (Bypasses Google login for instant local UI test)
DEV_LOGIN=1
```

### 3. Run Automated Pytest Suite

```bash
pytest
```
*Executes all 43 unit and concurrency tests verifying atomic seat allocations, duplicate suppression, timer expiry, and Google Sheets sync.*

### 4. Start Local Development Server

```bash
flask --app app run -p 5000
```
Open **`http://localhost:5000`** in your browser. With `DEV_LOGIN=1`, you can instantly test selection flows without live Google credentials.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## ⚙️ Production Deployment (Vercel & Neon)

### Step 1: Google Cloud Platform Setup
1. Open the [Google Cloud Console](https://console.cloud.google.com).
2. **Google OAuth 2.0 Client**:
   - Navigate to **APIs & Services** > **Credentials** > **Create Credentials** > **OAuth client ID**.
   - Select **Web application**.
   - Under **Authorized JavaScript origins**, add:
     - `https://faculty-selection-bitsathy.vercel.app`
     - `http://localhost:5000`
   - Copy the generated **Client ID** into `GOOGLE_CLIENT_ID`.
3. **Google Sheets Service Account**:
   - Enable the **Google Sheets API**.
   - Navigate to **IAM & Admin** > **Service Accounts** > **Create Service Account**.
   - Generate and download a **JSON Key**. Paste the contents into `GOOGLE_SERVICE_ACCOUNT_JSON`.
   - Open your target Google Sheet and share it with the service account email as **Editor**.

### Step 2: Vercel & Neon PostgreSQL Deployment
1. Import the repository into [Vercel](https://vercel.com).
2. Under **Storage**, create a **Neon PostgreSQL** database and link it to the project (this automatically populates `DATABASE_URL`).
3. Under **Settings > Environment Variables**, add:
   - `SECRET_KEY`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`
   - `GOOGLE_SHEET_ID`
   - `OPEN_AT` *(Optional: ISO-8601 timestamp e.g. `2026-10-07T10:00:00+05:30` to hold students until official start time)*
4. Deploy! Verify health via `https://faculty-selection-bitsathy.vercel.app/healthz`.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🛠️ Administrative CLI Tool (`manage.py`)

Run administrative operations locally or in production maintenance mode:

```bash
# 1. View live seat distribution and fill progress
python manage.py status

# 2. View all submitted selections in exact millisecond FCFS order
python manage.py list

# 3. Free a seat for a student (clears database record & clears Google Sheet row)
python manage.py reset 7376257MB101

# 4. Re-synchronize any pending/buffered offline rows to Google Sheets
python manage.py sync

# 5. Initialize Google Sheet tabs (Responses + Summary)
python manage.py init-sheet

# 6. Export the full allocation audit log to a local CSV backup
python manage.py export allocations_backup.csv
```

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 🧪 Quality Assurance & Test Matrix

The test suite covers 43 critical operational scenarios:

```
tests/test_allocation.py ......................... [ 58%]
tests/test_auth.py       .........                 [ 79%]
tests/test_sheets.py     .........                 [100%]
============================== 43 passed in 1.48s ==============================
```

- **Race Condition Resistance**: Verified with simulated multi-threaded concurrent requests attempting to seize the last available seat simultaneously.
- **Strict Single-Response Invariance**: Validated that duplicate clicks or back-button re-submissions do not register multiple entries.
- **Time Window Enforcement**: Submissions past 60 seconds (+2s network grace period) are strictly rejected.
- **Roster & Email Domain Enforcement**: Rejection of foreign email domains or unlisted student roll numbers.

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%" />

## 📜 License & Credits

Developed with ❤️ for **Bannari Amman Institute of Technology (BIT Sathy)** MBA Department.  
Licensed under the [MIT License](LICENSE).
