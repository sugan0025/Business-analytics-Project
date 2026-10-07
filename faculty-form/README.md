<!-- ═══════════════════════════════════════════════════════════════════════════════════ -->
<!-- ░░░  FACULTY GUIDE SELECTION — HIGH-CONCURRENCY FCFS PLATFORM  ░░░░░░░░░░░░░░░░░░░░ -->
<!-- ═══════════════════════════════════════════════════════════════════════════════════ -->

<!-- ╔═══════════════════════════════╗ -->
<!-- ║   ANIMATED GRADIENT HEADER    ║ -->
<!-- ╚═══════════════════════════════╝ -->
<div align="center">

<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/header-banner.svg" width="100%" alt="Faculty Guide Selection Animated Header" />

<br><br>

<!-- Animated Typing SVG (Single-line, no text overflow) -->
<a href="https://readme-typing-svg.demolab.com">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=19&duration=3000&pause=1000&color=38BDF8&center=true&vCenter=true&repeat=true&width=750&height=45&lines=High-Concurrency+FCFS+Faculty+Guide+Selection+Platform;Zero+Race+Conditions+%E2%80%A2+PostgreSQL+Row-Level+Locks;Instant+Sub-250ms+Auth+Latency+%E2%80%A2+Zero+Waterfall+Loading;Multi-Tab+Google+Sheets+API+v4+Reconciliation+Engine" alt="Typing SVG" />
</a>

<br><br>

<!-- Badges Row 1: Deployment & Stack -->
<a href="https://faculty-selection-bitsathy.vercel.app">
  <img src="https://img.shields.io/badge/%E2%96%B6_LIVE_PLATFORM-faculty--selection--bitsathy.vercel.app-38BDF8?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Platform" />
</a>
&nbsp;
<a href="https://www.python.org/">
  <img src="https://img.shields.io/badge/Python_3.12-Fast_WSGI-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12" />
</a>
&nbsp;
<a href="https://flask.palletsprojects.com/">
  <img src="https://img.shields.io/badge/Flask-Lightweight_Backend-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
</a>
&nbsp;
<a href="https://neon.tech">
  <img src="https://img.shields.io/badge/PostgreSQL-Neon_ACID_Locks-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
</a>

<br><br>

<!-- Badges Row 2: Cloud Sync, Auth & Performance -->
<img src="https://img.shields.io/badge/Google_Sheets_v4-Multi--Tab_Sync-34A853?style=for-the-badge&logo=googlesheets&logoColor=white" alt="Google Sheets Sync" />
&nbsp;
<img src="https://img.shields.io/badge/Google_OAuth-Institutional_JWT-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Identity" />
&nbsp;
<img src="https://img.shields.io/badge/Latency-Sub--250ms_Auth-10B981?style=for-the-badge&logo=speedtest&logoColor=white" alt="Sub-250ms Latency" />
&nbsp;
<img src="https://img.shields.io/badge/Test_Suite-43_Passing-238636?style=for-the-badge&logo=pytest&logoColor=white" alt="Pytest 43 Tests" />

<br><br>

<p align="center">
  <b>A mission-critical, high-concurrency web platform engineered for Bannari Amman Institute of Technology (BIT Sathy) II MBA students. Guarantees strict First-Come, First-Served (FCFS) fairness, sub-250ms authenticated latency, zero race conditions via PostgreSQL row locks, and multi-tab Google Sheets reconciliation with dedicated Faculty Portals and Test Simulation Modes.</b>
</p>

[⚡ Live Platform](https://faculty-selection-bitsathy.vercel.app) • [🏛️ System Architecture](#️-system-architecture) • [🔒 Concurrency Guarantees](#-concurrency--fairness-guarantees) • [👥 Faculty Portals](#-faculty-access--portal-features) • [📊 Google Sheets Sync](#-multi-tab-google-sheets-sync-v4) • [📁 Project Structure](#-project-directory-structure) • [🛠️ Admin CLI](#️-administrative-cli-tool-managepy)

</div>

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║       EXECUTIVE SUMMARY       ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>📌 Executive Overview &amp; Problem Statement</h2>

During institutional faculty advisor selection, dozens of students attempt to claim high-demand guides in the exact same millisecond. Generic forms (such as Google Forms or simple web apps) consistently fail under concurrent rush due to database race conditions, seat oversubscription, out-of-order writes, and spreadsheet locking.

**The Faculty Guide Selection Platform** was built to deliver mathematical fairness and instant response times:

```yaml
Deployment Status   : Production Live on Vercel Serverless (HTTP 200 OK)
Target Users        : Bannari Amman Institute of Technology (BIT Sathy) — II MBA Batch
Allocation Volume   : 44 Students • 10 Faculty Members (Default quotas: 5,5,5,5,4,4,4,4,4,4)
Core Problem Solved : Zero Race Conditions • Strict FCFS Fairness • Instant Google Sheets Sync
Engineering Stack   : Python 3.12 • Flask • PostgreSQL (Neon / Supabase) • Google Sheets API v4
Authentication      : Google Identity Services (OAuth 2.0 JWT) • In-Memory RSA Public Key Cache
Latency Profile     : Sub-250ms Authenticated Submission • Zero Waterfall Screen Flickering
Client Hardening    : iOS Safari 100dvh • Safe-Area Insets • Keyboard Hotkeys (1-9, Enter)
```

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║      SYSTEM ARCHITECTURE      ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>🏛️ System Architecture</h2>

<div align="center">
  <img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/architecture-diagram.svg" width="100%" alt="Faculty Guide Selection Real-Time System Architecture" />
</div>

<br>

| Architectural Pillar | Core Technology | Engineering Responsibility |
|---|---|---|
| **📱 Client Layer** | Vanilla JS (ES6+), Modern CSS (`100dvh`) | 60s countdown timer, 3s seat availability polling, zero-waterfall state preload, keyboard shortcuts |
| **🔑 Gateway &amp; Auth** | Google Identity Services, Vercel Edge | Strict `@bitsathy.ac.in` domain verification, in-memory RSA key caching (<50ms JWT validation), student roster binding |
| **🔒 Concurrency Engine** | PostgreSQL (`Neon`), `psycopg3` | Single-transaction `SELECT FOR UPDATE` row locks, atomic conditional updates, database `CHECK` constraints |
| **📊 Sheets Reconciliation** | Google Sheets API v4, Service Account | Deterministic 1-to-1 row indexing (`row = response_number + 1`), offline retry queue, multi-tab audit ledger |

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║  CONCURRENCY & FAIRNESS       ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>🔒 Concurrency &amp; Fairness Guarantees</h2>

The platform enforces 6 structural invariants to eliminate race conditions and maintain full audit integrity:

| Operational Invariant | Technical Implementation | Practical Guarantee |
|---|---|---|
| **Zero Oversubscription** | `UPDATE faculty SET selected_count = selected_count + 1 WHERE id = :id AND selected_count < capacity` + DB `CHECK (selected_count <= capacity)` | Impossible for any faculty guide to exceed assigned seat limit |
| **Millisecond FCFS Ledger** | PostgreSQL transaction row locking (`SELECT FOR UPDATE`) | In a tie between simultaneous claims, only the millisecond winner secures the slot |
| **Tamper-Proof Identity** | Cryptographic verification of Google OAuth JWT; student email verified against `roster.csv` | Students cannot impersonate peers or submit on behalf of others |
| **Idempotent Submission** | Unique database constraint on `student_email` and `register_number` | Accidental double-taps return the existing confirmation without duplicate seat consumption |
| **60-Second Selection Timer** | Server-side start timestamp recording with 2s network jitter tolerance | Prevents seat hoarding; late submissions past the timer window are rejected |
| **Offline Sync Resiliency** | PostgreSQL fallback queue with CLI re-push (`python manage.py sync`) | Google Sheet API rate limits or latency hiccups never block student selections |

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║   FACULTY PORTAL & PREVIEW    ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>👥 Faculty Access &amp; Portal Features</h2>

The system incorporates dual-role intelligence: students are routed directly to live allocation, while faculty members authenticate into a dedicated management portal.

* **Dedicated Faculty Dashboard**: When a verified faculty member logs in, they view real-time advisor capacity, remaining seat counters, and a live FCFS roster of students who have confirmed them as guide.
* **Google Forms-Style Preview Icon (👁️)**: Positioned in the header, allowing faculty to inspect the student experience with two specialized modes:
  - 📋 **Select Students (Faculty Preference)**: Allows faculty to select preferred student mentees; entries sync to the `Faculty Selections` Google Sheets tab.
  - 🧪 **Test Mode (Student Simulation)**: Simulates the student selection journey, enabling faculty to test the flow without consuming live student seat quotas (mirrored to `Test Responses`).

### Configured Faculty Roster

| Faculty Guide | Institutional Email | Status |
|---|---|---|
| **Prof. Suganesh S** | `suganeshs@bitsathy.ac.in` | ✅ Configured |
| **Prof. Senthil Kumar N** | `senthilkumar@bitsathy.ac.in` | ✅ Configured |
| **Prof. Mageswaran J** | `mageswaran@bitsathy.ac.in` | ✅ Configured |
| **Dr Murugappan S** | `murugappans@bitsathy.ac.in` | ✅ Configured |
| **Prof. Nandhini B** | `nandhinib@bitsathy.ac.in` | ✅ Configured |
| **Prof. Dhanabalu S N** | `dhanabalusn@bitsathy.ac.in` | ✅ Configured |
| **Dr Adhinarayanan B** | `adhinarayananb@bitsathy.ac.in` | ✅ Configured |
| **Prof. Aishwariya M R** | `aishwariya@bitsathy.ac.in` | ✅ Configured |

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║     GOOGLE SHEETS SYNC        ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>📊 Multi-Tab Google Sheets Sync v4</h2>

Selections mirror asynchronously to Google Sheets via service account credentials across 4 structured tabs:

1. **`Responses`** — Real student allocation records in exact chronological FCFS order with deterministic row indexing (`row = response_number + 1`).
2. **`Summary`** — Live aggregation tab utilizing dynamic `=COUNTIF` and `=SUM` spreadsheet formulas tracking quota fulfillment.
3. **`Faculty Selections`** — Records official faculty student preferences submitted through the Faculty Portal.
4. **`Test Responses`** — Isolated ledger for simulated student walkthroughs during pre-run testing.

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║    PROJECT DIRECTORY MAP      ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>🗂️ Project Directory Structure</h2>

```
Business-analytics-Project/
├── 📂 assets/                              # High-resolution vector diagrams & UI assets
│   ├── 🎨 header-banner.svg                # Dark-mode glowing header banner
│   ├── 🏛️ architecture-diagram.svg         # 4-stage end-to-end architecture breakdown
│   └── 🌈 rainbow-divider.svg              # Animated gradient section divider
│
├── 📂 faculty-form/
│   ├── 📂 api/
│   │   └── index.py                        # Vercel serverless WSGI entry gateway
│   ├── 📂 public/
│   │   ├── form.js                         # State machine, 60s timer, Faculty Portal, keyboard hotkeys
│   │   └── styles.css                      # Modern responsive styling, 100dvh, iOS safe areas
│   ├── 📂 templates/
│   │   └── index.html                      # Accessible server-rendered HTML template with preloaded state
│   ├── 📂 tests/                           # 43 automated unit, concurrency & failure test cases
│   │   ├── conftest.py                     # Mock fixtures for Google OAuth and Sheets API
│   │   ├── test_allocation.py              # FCFS concurrency and capacity tests
│   │   ├── test_auth.py                    # JWT parsing, domain check, and key caching tests
│   │   └── test_sheets.py                  # Idempotent reconciliation and retry buffer tests
│   │
│   ├── ⚡ app.py                           # Flask routes, preloaded state injection & REST endpoints
│   ├── 🔑 auth.py                          # Google OAuth 2.0 verification & in-memory RSA key cache
│   ├── 🔒 allocation.py                    # Atomic transaction and row-level locking engine
│   ├── 💾 db.py                            # PostgreSQL connection pool with local SQLite fallback
│   ├── 📊 sheets_sync.py                   # Multi-tab Google Sheets API background worker
│   ├── ⚙️ config.py                         # Environment variables and configuration loader
│   ├── 🛠️ manage.py                        # Administrative CLI tool (status, list, reset, sync, export)
│   ├── 📋 faculty.csv                      # 10 faculty guides with seat quotas and verified emails
│   ├── 🎓 roster.csv                       # 44 authorized student roll numbers and institutional emails
│   ├── 📦 requirements.txt                 # Production serverless dependencies
│   └── 🧪 requirements-dev.txt             # Development and testing dependencies
```

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║     LOCAL SETUP GUIDE         ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>🚀 Local Setup &amp; Development</h2>

### 1. Clone & Environment Setup
```bash
git clone https://github.com/sugan0025/Business-analytics-Project.git
cd Business-analytics-Project/faculty-form

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and provide your credentials:

| Variable | Description | Required | Default |
|---|---|:---:|---|
| `SECRET_KEY` | Flask session cryptographic key | Yes | Random string |
| `GOOGLE_CLIENT_ID` | Google Cloud OAuth 2.0 Web Client ID | Yes (Prod) | — |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON service account key string | Yes (Prod) | — |
| `GOOGLE_SHEET_ID` | Target Google Spreadsheet ID | Yes (Prod) | `1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI` |
| `DATABASE_URL` | PostgreSQL connection URL (Neon / Supabase) | Yes (Prod) | SQLite `faculty.db` |
| `ALLOWED_EMAIL_DOMAIN` | Restrict auth to institutional domain | No | `bitsathy.ac.in` |
| `SELECTION_WINDOW_SECONDS` | Fair-play selection countdown window | No | `60` |
| `DEV_LOGIN` | Bypass Google login for offline local testing | No | `0` (set `1` for local) |

### 3. Run Test Suite
```bash
pytest
# Executes all 43 concurrency, capacity, auth, and Sheets tests
```

### 4. Start Local Development Server
```bash
flask --app app run -p 5000
# Live on http://localhost:5000
```

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║    ADMIN & CLI COMMANDS       ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>🛠️ Administrative CLI Tool (`manage.py`)</h2>

Execute administrative audit and reconciliation operations directly from the terminal:

```bash
# View live faculty seat counts and fill percentages
python manage.py status

# List all submitted selections in exact millisecond FCFS order
python manage.py list

# Free a seat for a student (clears database & clears Google Sheets row)
python manage.py reset 7376257MB101

# Re-push any pending/buffered rows to Google Sheets
python manage.py sync

# Initialize Google Sheet tabs (Responses, Summary, Faculty Selections, Test Responses)
python manage.py init-sheet

# Export full allocation audit dataset to CSV
python manage.py export export.csv
```

<!-- Animated Glowing Divider -->
<img src="https://cdn.jsdelivr.net/gh/sugan0025/Business-analytics-Project@main/assets/rainbow-divider.svg" width="100%">

<!-- ╔═══════════════════════════════╗ -->
<!-- ║    AUTHOR & CREDITS           ║ -->
<!-- ╚═══════════════════════════════╝ -->

<h2>👨‍💻 Author &amp; Credits</h2>

```yaml
Architect           : Suganesan S (Sugan)
Institution         : Bannari Amman Institute of Technology (BIT Sathy)
Department          : School of Management Studies (II MBA Batch)
Live URL            : https://faculty-selection-bitsathy.vercel.app
GitHub Repository   : https://github.com/sugan0025/Business-analytics-Project
```

<div align="center">

<a href="https://faculty-selection-bitsathy.vercel.app">
  <img src="https://img.shields.io/badge/%E2%9A%A1_Experience_Faculty_Selection-38BDF8?style=for-the-badge&logoColor=white" />
</a>
&nbsp;
<a href="https://github.com/sugan0025">
  <img src="https://img.shields.io/badge/GitHub-sugan0025-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>

<br><br>

<b>Faculty Guide Selection Platform</b> • Built with ❤️ for BIT Sathy MBA • Licensed under the MIT License.

</div>
