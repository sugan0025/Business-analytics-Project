# Faculty Guide Selection ⚡

> High-concurrency, real-time faculty guide selection platform with zero race conditions, sub-250ms authenticated latency, automatic Google Sheets reconciliation, and dedicated Faculty Access Portals.

Built with **Python 3.12 · Flask · PostgreSQL · Vercel Serverless · Google Sheets API v4 · Google Identity Services · Vanilla JS · Modern CSS**.

🔗 **Live Deployment:** [faculty-selection-bitsathy.vercel.app](https://faculty-selection-bitsathy.vercel.app)

---

## 🌟 Features

- **Atomic FCFS Seat Allocation** — Single-transaction row-level locking (`SELECT FOR UPDATE` / atomic conditional updates) ensures two students can never claim the same last seat simultaneously.
- **Institutional Google OAuth & Role Routing** — Strict `@bitsathy.ac.in` institutional domain authentication. Students are routed to live allocation, while faculty members access their dedicated Faculty Portal.
- **Dedicated Faculty Portal** — Real-time dashboard showing faculty guide capacity, current seat count, and a live FCFS table of students who have selected them.
- **Google Forms-Style Preview Icon (👁️)** — Top right preview icon allowing faculty to inspect how the form looks, with two dedicated modes:
  - 📋 **Select Students (Faculty Preference)**: Faculty can select students they wish to guide, recorded as official faculty selection data in the `Faculty Selections` Google Sheets tab.
  - 🧪 **Test Mode (Student Simulation)**: Faculty can simulate student selection, picking any faculty (including their own name) to test the flow. Submissions are recorded in a separate `Test Responses` Google Sheets tab without consuming real student quotas.
- **Sub-250ms Instant Experience** — Zero waterfall loading; returns preloaded state directly upon authentication, eliminating jarring spinners and intermediate screen flicker.
- **Google Public Key Caching** — In-memory caching of Google's RSA public certificates with automatic TTL expiry, reducing auth roundtrips from ~1.5s to under 50ms.
- **Multi-Tab Google Sheets Sync** — Confirmed responses sync instantly to Google Sheets across dedicated tabs:
  - `Responses` — Real student selections in exact millisecond order.
  - `Summary` — Dynamic quota formula counters (`=COUNTIF`, `=SUM`).
  - `Faculty Selections` — Faculty student mentor selections.
  - `Test Responses` — Faculty test simulation entries.
- **60-Second Selection Timer** — Countdown timer to prevent seat hoarding during active allocation rush.
- **Cross-Browser & Mobile Hardened** — Fully optimized for iOS Safari (`100dvh`, notch safe-areas, `-webkit-tap-highlight-color: transparent`), Android Chrome, and Firefox.
- **Keyboard Quick Navigation** — Instant number key selection (`1-9`, `0`) and hotkey confirmations for lightning-fast submission.

---

## 👥 Faculty Access

Faculty members sign in directly using their institutional Google Workspace accounts (`@bitsathy.ac.in`):

| Faculty Guide | College Email | Status |
|---|---|---|
| **Prof. Suganesh S** | `suganeshs@bitsathy.ac.in` | ✅ Configured |
| **Prof. Senthil Kumar N** | `senthilkumar@bitsathy.ac.in` | ✅ Configured |
| **Prof. Mageswaran J** | `mageswaran@bitsathy.ac.in` | ✅ Configured |
| **Dr Murugappan S** | `murugappans@bitsathy.ac.in` | ✅ Configured |
| **Prof. Nandhini B** | `nandhinib@bitsathy.ac.in` | ✅ Configured |
| **Prof. Dhanabalu S N** | `dhanabalusn@bitsathy.ac.in` | ✅ Configured |
| **Dr Adhinarayanan B** | `adhinarayananb@bitsathy.ac.in` | ✅ Configured |
| **Prof. Aishwariya M R** | `aishwariya@bitsathy.ac.in` | ✅ Configured |
| *Additional Faculty (2)* | *Added directly via `faculty.csv`* | 🔄 Extensible |

---

## ⚡ Quick start

```bash
# 1. Clone repository
git clone https://github.com/sugan0025/Business-analytics-Project.git
cd Business-analytics-Project/faculty-form

# 2. Set up virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# 👉 Add GOOGLE_CLIENT_ID
# 👉 Add GOOGLE_SERVICE_ACCOUNT_JSON
# 👉 Add DATABASE_URL (or leave blank to use local SQLite)
# 👉 Set DEV_LOGIN=1 for testing locally without Google credentials

# 5. Start local development server
flask --app app run -p 5000
```

Open http://localhost:5000 — the app is running locally.

---

## 🔑 Environment Variables & Setup

Create a `.env` file inside `faculty-form/` based on `.env.example`:

| Variable | Description | Required | Default |
|---|---|---|---|
| `SECRET_KEY` | Session signing secret key | Yes | Random string |
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 Web Client ID | Yes (Production) | — |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON credentials for Google Sheets API | Yes (Production) | — |
| `GOOGLE_SHEET_ID` | Google Spreadsheet ID for live responses | Yes (Production) | `1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI` |
| `DATABASE_URL` | PostgreSQL connection string (Neon / Supabase) | Yes (Production) | SQLite `faculty.db` |
| `ALLOWED_EMAIL_DOMAIN` | Institutional email domain | No | `bitsathy.ac.in` |
| `SELECTION_WINDOW_SECONDS` | Time allotted to select faculty | No | `60` |
| `DEV_LOGIN` | Bypass Google login for offline testing | No | `0` |

---

## 📁 Project structure

```
Business-analytics-Project/
└── faculty-form/
    ├── app.py              # Flask app, preloaded state & REST APIs
    ├── auth.py             # Google OAuth JWT validation, role routing & RSA key cache
    ├── allocation.py       # Atomic FCFS seat allocation logic
    ├── db.py               # PostgreSQL connection pool & SQLite fallback
    ├── sheets_sync.py      # Multi-tab Google Sheets API background reconciliation
    ├── config.py           # Configuration & environment loader
    ├── manage.py           # Organiser CLI (status, list, reset, sync, export)
    ├── roster.csv          # Student roster with verified college emails
    ├── faculty.csv         # Faculty list, seat limits & faculty emails
    ├── api/
    │   └── index.py        # Vercel serverless gateway
    ├── public/
    │   ├── form.js         # Frontend logic, Faculty Portal, Preview & Test Modes
    │   └── styles.css      # Modern responsive styles (100dvh, iOS fixes, Table UI)
    └── templates/
        └── index.html      # Accessible form template
```

---

## 🛠️ Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + Flask |
| Serverless | Vercel Serverless Functions (`@vercel/python`) |
| Database | PostgreSQL (Neon / Supabase) + `psycopg3` / SQLite |
| Cloud Integration | Google Sheets API v4 (`google-api-python-client`) |
| Authentication | Google Identity Services (OAuth 2.0 JWT) |
| Frontend | Vanilla JavaScript (ES6+), Modern CSS (100dvh, Glassmorphism) |

---

## 📋 Admin & CLI commands

Manage allocations, audit logs, and sheet synchronization directly from the terminal:

```bash
# View live faculty seat counts and fill status
python manage.py status

# List all submitted selections in exact FCFS order
python manage.py list

# Free a seat for a student (clears database & Google Sheets row)
python manage.py reset 7376257MB101

# Re-push any pending/buffered rows to Google Sheets
python manage.py sync

# Initialize Google Sheet tabs (Responses, Summary, Faculty Selections, Test Responses)
python manage.py init-sheet

# Export full allocation dataset to CSV
python manage.py export export.csv
```

---

## 📄 License

MIT
