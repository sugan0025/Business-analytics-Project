"""Push committed selections, faculty choices, and test responses to Google Sheets.

Each selection is written to a fixed row (row = seq_id + 1, header is row 1), so a retry or two
overlapping syncs just rewrite the same cells: duplicates are impossible, and the sheet order always
equals the FCFS order regardless of which request finishes first.
Selections are safe in the database even if the sheet is down; unsynced rows are retried on the next call.
"""
import json
import logging
from typing import List, Tuple

from sqlalchemy import select, update

from config import Settings, fmt_ist
from db import faculty, faculty_student_selections, selections, test_selections

log = logging.getLogger("faculty-form")

HEADERS = ["Seq No", "Timestamp (IST)", "Name", "Register No", "Email", "Faculty"]
FACULTY_HEADERS = ["Entry ID", "Timestamp (IST)", "Faculty Name", "Faculty Email", "Selected Student Reg No", "Selected Student Name"]
TEST_HEADERS = ["Test ID", "Timestamp (IST)", "Tester / Faculty", "Tester Email", "Selected Faculty Choice", "Status"]

SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def row_values(sel: dict) -> list:
    return [sel["seq_id"], fmt_ist(sel["created_ms"]), sel["student_name"], sel["register_no"],
            sel["email"], sel["faculty_name"]]


class GoogleSheetsClient:
    """Minimal Sheets REST client using a service account (no heavy Google SDK needed)."""

    def __init__(self, settings: Settings):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
        if settings.service_account_json:
            info = json.loads(settings.service_account_json)
        else:
            with open(settings.service_account_file, encoding="utf-8") as f:
                info = json.load(f)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self.session = AuthorizedSession(creds)
        self.sheet_id = settings.sheet_id
        self.responses_tab = settings.responses_tab
        self.summary_tab = settings.summary_tab
        self.faculty_tab = "Faculty Selections"
        self.test_tab = "Test Responses"
        self.service_account_email = info.get("client_email", "")

    def _call(self, method, path, **kwargs):
        resp = self.session.request(method, f"{SHEETS_API}/{self.sheet_id}{path}", timeout=8, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sheets API {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    def ensure_tab(self, title: str, headers: list):
        try:
            meta = self._call("GET", "?fields=sheets.properties.title")
            have = {s["properties"]["title"] for s in meta.get("sheets", [])}
            if title not in have:
                self._call("POST", ":batchUpdate", json={"requests": [{"addSheet": {"properties": {"title": title}}}]})
                self._call("POST", "/values:batchUpdate", json={
                    "valueInputOption": "RAW",
                    "data": [{"range": f"'{title}'!A1:F1", "values": [headers]}]
                })
        except Exception:
            log.exception(f"Error ensuring sheet tab {title}")

    # -- used on student selection sync
    def write_rows(self, rows: List[Tuple[int, list]]):
        data = [{"range": f"'{self.responses_tab}'!A{n}:F{n}", "values": [vals]} for n, vals in rows]
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": data})

    def write_faculty_rows(self, rows: List[Tuple[int, list]]):
        self.ensure_tab(self.faculty_tab, FACULTY_HEADERS)
        data = [{"range": f"'{self.faculty_tab}'!A{n}:F{n}", "values": [vals]} for n, vals in rows]
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": data})

    def write_test_rows(self, rows: List[Tuple[int, list]]):
        self.ensure_tab(self.test_tab, TEST_HEADERS)
        data = [{"range": f"'{self.test_tab}'!A{n}:F{n}", "values": [vals]} for n, vals in rows]
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": data})

    def clear_rows(self, row_numbers: List[int]):
        ranges = [f"'{self.responses_tab}'!A{n}:F{n}" for n in row_numbers]
        self._call("POST", "/values:batchClear", json={"ranges": ranges})

    def read_responses(self) -> list:
        try:
            res = self._call("GET", f"/values/'{self.responses_tab}'!A:F")
            return res.get("values", [])
        except Exception:
            log.exception("Error reading responses from Google Sheet")
            return []

    def delete_student_by_query(self, reg_no: str, email: str) -> list:
        rows = self.read_responses()
        cleared_indices = []
        reg_upper = (reg_no or "").strip().upper()
        email_lower = (email or "").strip().lower()

        for idx, row in enumerate(rows, start=1):
            if idx == 1:
                continue  # header
            row_reg = (row[3] if len(row) > 3 else "").strip().upper()
            row_email = (row[4] if len(row) > 4 else "").strip().lower()
            if (reg_upper and row_reg == reg_upper) or (email_lower and row_email == email_lower):
                cleared_indices.append(idx)

        if cleared_indices:
            self.clear_rows(cleared_indices)
            log.info(f"Cleared rows from Google Sheet: {cleared_indices}")
        return cleared_indices

    def count_selections_by_faculty(self) -> dict:
        rows = self.read_responses()
        counts = {}
        for idx, row in enumerate(rows, start=1):
            if idx == 1:
                continue
            if len(row) > 5 and row[5].strip():
                fac_name = row[5].strip()
                counts[fac_name] = counts.get(fac_name, 0) + 1
        return counts

    # -- one-time layout (manage.py init-sheet)
    def init_layout(self, faculty_rows: List[dict]):
        meta = self._call("GET", "?fields=sheets.properties.title")
        have = {s["properties"]["title"] for s in meta.get("sheets", [])}
        add = [{"addSheet": {"properties": {"title": t}}}
               for t in (self.responses_tab, self.summary_tab, self.faculty_tab, self.test_tab) if t not in have]
        if add:
            self._call("POST", ":batchUpdate", json={"requests": add})
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": [
            {"range": f"'{self.responses_tab}'!A1:F1", "values": [HEADERS]},
            {"range": f"'{self.faculty_tab}'!A1:F1", "values": [FACULTY_HEADERS]},
            {"range": f"'{self.test_tab}'!A1:F1", "values": [TEST_HEADERS]},
        ]})
        summary = [["Faculty", "Capacity", "Selected", "Remaining"]]
        for i, f in enumerate(faculty_rows, start=2):
            summary.append([f["name"], f["capacity"],
                            f"=COUNTIF('{self.responses_tab}'!F:F,A{i})", f"=B{i}-C{i}"])
        last = len(summary)
        summary.append(["Total", f"=SUM(B2:B{last})", f"=SUM(C2:C{last})", f"=SUM(D2:D{last})"])
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "USER_ENTERED", "data": [
            {"range": f"'{self.summary_tab}'!A1:D{len(summary)}", "values": summary},
        ]})


def get_client(settings: Settings):
    """Real client if credentials are configured, otherwise None (sync is skipped)."""
    if not (settings.service_account_json or settings.service_account_file):
        return None
    return GoogleSheetsClient(settings)


def sync_pending(engine, client, limit: int = 100) -> dict:
    """Write all unsynced selections, faculty student choices, and test submissions to the sheet."""
    if client is None:
        return {"synced": 0, "pending": None, "error": "sheets_not_configured"}

    # 1. Sync student selections to Responses tab
    with engine.connect() as conn:
        rows = conn.execute(
            select(selections, faculty.c.name.label("faculty_name"))
            .join(faculty, faculty.c.id == selections.c.faculty_id)
            .where(selections.c.synced == 0).order_by(selections.c.seq_id).limit(limit)
        ).mappings().all()

    if rows:
        try:
            client.write_rows([(r["seq_id"] + 1, row_values(r)) for r in rows])
            with engine.begin() as conn:
                conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                             .values(synced=1, sync_error=None))
        except Exception as exc:
            msg = str(exc)[:500]
            with engine.begin() as conn:
                conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                             .values(sync_error=msg))

    # 2. Sync faculty student selections to Faculty Selections tab
    try:
        with engine.connect() as conn:
            fac_rows = conn.execute(
                select(faculty_student_selections).where(faculty_student_selections.c.synced == 0)
                .order_by(faculty_student_selections.c.id).limit(limit)
            ).mappings().all()
        if fac_rows:
            f_data = [
                (r["id"] + 1, [
                    r["id"], fmt_ist(r["created_ms"]), r["faculty_name"], r["faculty_email"],
                    r["student_register_no"], r["student_name"]
                ]) for r in fac_rows
            ]
            client.write_faculty_rows(f_data)
            with engine.begin() as conn:
                conn.execute(update(faculty_student_selections)
                             .where(faculty_student_selections.c.id.in_([r["id"] for r in fac_rows]))
                             .values(synced=1, sync_error=None))
    except Exception:
        log.exception("Error syncing faculty student selections to sheets")

    # 3. Sync test responses to Test Responses tab
    try:
        with engine.connect() as conn:
            t_rows = conn.execute(
                select(test_selections).where(test_selections.c.synced == 0)
                .order_by(test_selections.c.id).limit(limit)
            ).mappings().all()
        if t_rows:
            t_data = [
                (r["id"] + 1, [
                    f"TEST-{r['id']}", fmt_ist(r["created_ms"]), r["tester_name"], r["tester_email"],
                    r["faculty_name"], "Test Simulation"
                ]) for r in t_rows
            ]
            client.write_test_rows(t_data)
            with engine.begin() as conn:
                conn.execute(update(test_selections)
                             .where(test_selections.c.id.in_([r["id"] for r in t_rows]))
                             .values(synced=1, sync_error=None))
    except Exception:
        log.exception("Error syncing test submissions to sheets")

    return {"synced": len(rows), "pending": 0, "error": None}


def reconcile_sheet_and_db(engine, client) -> dict:
    """Two-way synchronization between Google Sheet and database:
    1. Clear Suganesan S (7376257MB144 / suganesans.mb25@bitsathy.ac.in) from Google Sheet Responses tab.
    2. Count remaining student choices in Responses tab per faculty.
    3. Update database table `faculty`:
       - Correct capacities: 5 for IDs (2, 3, 4), and 4 for IDs (5, 6, 7, 8, 9, 10).
       - Set selected_count to match Google Sheet selection counts dynamically.
    4. Remove any database records for Suganesan (selections and attempts).
    """
    if client is None:
        return {"ok": False, "error": "sheets_client_none"}

    try:
        cleared = client.delete_student_by_query("7376257MB144", "suganesans.mb25@bitsathy.ac.in")
        counts = client.count_selections_by_faculty()

        with engine.begin() as conn:
            # Enforce correct capacities
            conn.execute(update(faculty).where(faculty.c.id.in_([2, 3, 4])).values(capacity=5))
            conn.execute(update(faculty).where(faculty.c.id.in_([5, 6, 7, 8, 9, 10])).values(capacity=4))

            # Reconcile selected_count if Google Sheet has responses
            if counts:
                fac_rows = conn.execute(select(faculty)).mappings().all()
                for f in fac_rows:
                    cnt = counts.get(f["name"], 0)
                    conn.execute(update(faculty).where(faculty.c.id == f["id"]).values(selected_count=cnt))

            # Ensure Suganesan's student test record is deleted from DB
            from db import attempts, selections
            conn.execute(selections.delete().where(
                (selections.c.register_no == "7376257MB144") |
                (selections.c.email == "suganesans.mb25@bitsathy.ac.in")
            ))
            conn.execute(attempts.delete().where(attempts.c.email == "suganesans.mb25@bitsathy.ac.in"))

        return {"ok": True, "cleared_rows": cleared, "counts": counts}
    except Exception as exc:
        log.exception("Error in reconcile_sheet_and_db")
        return {"ok": False, "error": str(exc)}
