# Faculty Guide Selection System

> **A high-concurrency, FCFS faculty selection platform with zero race conditions, sub-250ms authenticated latency, and real-time Google Sheets reconciliation.**

🔗 **Live Application:** [faculty-selection-bitsathy.vercel.app](https://faculty-selection-bitsathy.vercel.app)  
📄 **Hackathon Presentation Brief:** [`Faculty_Guide_Selection_Hackathon.pdf`](Faculty_Guide_Selection_Hackathon.pdf)

---

## 📌 Overview

A streamlined, Google Forms-inspired selection application engineered for high-concurrency student allocation:
* **Strict College OAuth & Verification:** Students authenticate with institute Google Workspace accounts (`@bitsathy.ac.in`). Register numbers and names are securely bound to roster entries.
* **Atomic FCFS Seat Claims:** Database-level transactional locking (`SELECT FOR UPDATE` / atomic UPDATE) prevents race conditions, ensuring no two students can ever claim the same final seat.
* **Sub-250ms Latency:** Optimized post-login pipeline with Google RSA public key caching, preloaded dashboard states, and single-connection database pooling.
* **Serverless Google Sheets Sync:** Every confirmed selection is mirrored directly to Google Sheets with zero duplicate entries and resilient offline buffering.
* **Mobile & Cross-Browser Hardened:** Native-feeling web app supporting iOS Safari (`100dvh`, notch safe-areas), Android Chrome, Firefox, and desktop browsers.

---

## 📂 Repository Structure

```
.
├── Faculty_Guide_Selection_Hackathon.pdf   # 2-Page Executive Hackathon PDF Brief
├── generate_hackathon_pdf.py               # Automated PDF generator with ReportLab
├── pdf_assets/                             # High-resolution charts, SVGs, and UI captures
└── faculty-form/                           # Complete Web Application
    ├── app.py                              # Flask application & optimized REST APIs
    ├── auth.py                             # Fast Google JWT verification & cert cache
    ├── allocation.py                       # Atomic seat locking & allocation logic
    ├── db.py                               # PostgreSQL / SQLite connection pooling
    ├── sheets_sync.py                      # Google Sheets API background sync
    ├── config.py                           # Application configuration
    ├── manage.py                           # CLI admin tools (reset, sync, audit)
    ├── roster.csv                          # Student roster with verified emails
    ├── faculty.csv                         # Faculty list with seat caps
    ├── api/
    │   └── index.py                        # Vercel serverless gateway
    ├── static/                             # Frontend styles, scripts & icons
    └── tests/                              # Pytest test suite (43 test cases)
```

---

## ⚡ Tech Stack & Architecture

| Layer | Technology | Key Responsibility |
|---|---|---|
| **Frontend** | Vanilla JS, Modern CSS (100dvh, Glassmorphism) | Smooth state transitions, keyboard navigation (1-9, 0), zero flicker |
| **Backend** | Python 3.12, Flask, Vercel Serverless | Stateless API endpoints, fast token validation |
| **Database** | PostgreSQL (Neon / Supabase) | Atomic row-level locking for seat allocation |
| **Integration**| Google Sheets API v4 | Real-time synchronized responses & summary tab |
| **Auth** | Google OAuth 2.0 (Identity Services) | Strict institutional domain & roster validation |

---

## 🚀 Quick Start (Local Development)

```bash
cd faculty-form

# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Run comprehensive test suite
pytest

# 4. Start local development server
cp .env.example .env
flask --app app run -p 5000
```

---

## 🛠️ Admin & CLI Operations

Manage the allocation session via `manage.py`:

```bash
# View current faculty seat fill status
python manage.py status

# List all allocations in exact FCFS order
python manage.py list

# Free a seat for a specific student
python manage.py reset <REGISTER_NUMBER>

# Sync pending database responses to Google Sheets
python manage.py sync
```

---

## 📄 Documentation

For in-depth setup, Google Cloud credentials provisioning, and Vercel environment variable settings, see the detailed [Faculty Form Documentation](faculty-form/README.md).
