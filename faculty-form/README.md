# Faculty Selection Form

A Google-Form-style page where students pick one faculty member, first come first served.
10 faculty, 44 students (default seats 5,5,5,5,4,4,4,4,4,4). Students sign in with their college
Google account, get 60 seconds to submit, and every response is mirrored to a Google Sheet.

- Seats are claimed by the database in one atomic step, so two students can never get the same last seat.
- A faculty greys out ("Full") for everyone as soon as it fills. Counts refresh every 3 seconds.
- One response per student. Changing it needs the organiser (`manage.py reset`).
- The app does not use a server that stays on: it runs as a Vercel serverless function with a Postgres database.

```
app.py            Flask routes            auth.py         Google token + roster check
allocation.py     FCFS seat claim         sheets_sync.py  writes rows to the Google Sheet
db.py             tables + CSV seeding    config.py       settings (environment variables)
faculty.csv       names + seat counts     roster.csv      the 44 students (+ email column)
manage.py         organiser commands      api/index.py    Vercel entry point
templates/ public/   the form page        tests/          43 tests
```

## 1. Before the real run: fill in `roster.csv`

Add each student's college email in the `email` column (`name.mb25@bitsathy.ac.in`).
Once any email is filled in, the app switches to **strict mode**: a student can only sign in with an email
on the list, and it is tied to exactly one register number, so nobody can submit for someone else.
If the column stays empty, the app runs in a weaker mode where students pick their own register
number (anyone with a college account could choose someone else's). Don't open the form to students in that mode.

Seat counts live in `faculty.csv`. The app loads both files automatically when they change.

The email domain defaults to `bitsathy.ac.in` (the institute's real domain). Your brief said `bitsasthy`.
If your students' emails really use that spelling, set `ALLOWED_EMAIL_DOMAIN=bitsasthy.ac.in`.

## 2. Google setup (once)

1. Go to https://console.cloud.google.com and create a project.
2. **Google Sign-In:** APIs & Services -> OAuth consent screen (choose *Internal* if your college Google
   Workspace lets you, otherwise *External*, then publish it or add students as test users). Then Credentials ->
   Create credentials -> OAuth client ID -> *Web application*. Under **Authorized JavaScript origins** add your
   live link (for example `https://your-app.vercel.app`) and `http://localhost:5000` for local tests.
   Copy the **Client ID** -> this is `GOOGLE_CLIENT_ID`.
3. **Sheet access:** enable the *Google Sheets API*. Create a **service account** (IAM & Admin -> Service accounts),
   open it -> Keys -> Add key -> JSON. Open the downloaded file, copy its whole contents -> this is
   `GOOGLE_SERVICE_ACCOUNT_JSON`.
4. Open your Google Sheet -> Share -> paste the service account's email (`...@...iam.gserviceaccount.com`) as **Editor**.

## 3. Deploy on Vercel (gives you the shareable link)

1. Put this folder in a GitHub repository (the `.gitignore` already keeps secrets out) and import it at vercel.com.
   Or run `npx vercel` in this folder.
2. In the Vercel project: **Storage -> Create -> Neon (Postgres)** and connect it to the project. This adds
   `DATABASE_URL` automatically. (SQLite can't be used on Vercel because its files don't persist.)
3. **Settings -> Environment Variables**, add:

   | Name | Value |
   |---|---|
   | `SECRET_KEY` | any long random string |
   | `GOOGLE_CLIENT_ID` | from step 2 above |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | the whole key file, pasted |
   | `GOOGLE_SHEET_ID` | `1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI` (already the default) |
   | `OPEN_AT` | optional, e.g. `2026-10-07T10:00:00+05:30` so everyone starts together |
   | `SYNC_TOKEN` | optional, a secret for manually re-pushing rows to the sheet |

   The other options are listed in `.env.example`.
4. Redeploy. Open `https://<your-app>.vercel.app/healthz`. It should show `"ok": true` and
   `"sheets_configured": true`. Add the live URL to the OAuth client's Authorized JavaScript origins (step 2).
5. Create the sheet tabs once (from your computer, see section 4): `python manage.py init-sheet`.
6. Dress rehearsal: sign in with your own email, submit once, check the sheet row, then free the seat with
   `python manage.py reset <your register number>`.
7. Share the link.

## 4. Organiser commands (run on your computer)

```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# put the same DATABASE_URL (and GOOGLE_* values) in a local .env file first
python manage.py status            # seats per faculty
python manage.py list              # every selection in FCFS order
python manage.py reset 7376257MB101   # free one student's seat (also clears their sheet row)
python manage.py sync              # re-push any rows that failed to reach the sheet
python manage.py init-sheet        # create the Responses + Summary tabs
python manage.py export out.csv    # backup as CSV
```

If the Google Sheet is ever unreachable, students still get their seats. Rows are saved in the database and
pushed to the sheet on the next submission (or with `manage.py sync`). Each response always lands on the same sheet
row (row = response number + 1), so a retry can never create duplicates.

## 5. Run locally

```
pip install -r requirements-dev.txt
python -m pytest                                  # 43 tests: capacity, duplicates, timer, auth, concurrency, sheets
cp .env.example .env                              # then set DEV_LOGIN=1 to try it without Google
python -m flask --app app run -p 5000             # http://localhost:5000
```

Without `DATABASE_URL` it uses a local SQLite file (`faculty.db`). `DEV_LOGIN` is ignored on Vercel production.

## How the fairness guarantees work

| Rule | How it's enforced |
|---|---|
| Capacity never exceeded | `UPDATE faculty SET selected_count = selected_count + 1 WHERE selected_count < capacity`, plus a database CHECK constraint |
| Two students, one last seat | The database serialises that update, so only one request wins |
| One response per student | UNIQUE email and register number; repeat taps return the same confirmation |
| Can't submit for someone else | Identity comes from Google's signed token and the session, never from the form |
| 1-minute limit | Server records the start time and rejects late submits (2s network grace); the page clock is only a display |
| Data only on submit | Nothing is written until a submission succeeds |
