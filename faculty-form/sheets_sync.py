"""Push committed selections to Google Sheets.

Each selection is written to a fixed row (row = seq_id + 1, header is row 1), so a retry or two
overlapping syncs just rewrite the same cells: duplicates are impossible, and the sheet order always
equals the FCFS order regardless of which request finishes first.
Selections are safe in the database even if the sheet is down; unsynced rows are retried on the next call.
"""
import json
from typing import List, Tuple

from sqlalchemy import select, update

from config import Settings, fmt_ist
from db import faculty, selections

HEADERS = ["Seq No", "Timestamp (IST)", "Name", "Register No", "Email", "Faculty"]
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
        self.service_account_email = info.get("client_email", "")

    def _call(self, method, path, **kwargs):
        resp = self.session.request(method, f"{SHEETS_API}/{self.sheet_id}{path}", timeout=8, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sheets API {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    # -- used on every sync
    def write_rows(self, rows: List[Tuple[int, list]]):
        data = [{"range": f"'{self.responses_tab}'!A{n}:F{n}", "values": [vals]} for n, vals in rows]
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": data})

    def clear_rows(self, row_numbers: List[int]):
        ranges = [f"'{self.responses_tab}'!A{n}:F{n}" for n in row_numbers]
        self._call("POST", "/values:batchClear", json={"ranges": ranges})

    # -- one-time layout (manage.py init-sheet)
    def init_layout(self, faculty_rows: List[dict]):
        meta = self._call("GET", "?fields=sheets.properties.title")
        have = {s["properties"]["title"] for s in meta.get("sheets", [])}
        add = [{"addSheet": {"properties": {"title": t}}}
               for t in (self.responses_tab, self.summary_tab) if t not in have]
        if add:
            self._call("POST", ":batchUpdate", json={"requests": add})
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": [
            {"range": f"'{self.responses_tab}'!A1:F1", "values": [HEADERS]},
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
    """Write all unsynced selections to the sheet. Never raises; failures are recorded and retried later."""
    if client is None:
        return {"synced": 0, "pending": None, "error": "sheets_not_configured"}
    with engine.connect() as conn:
        rows = conn.execute(
            select(selections, faculty.c.name.label("faculty_name"))
            .join(faculty, faculty.c.id == selections.c.faculty_id)
            .where(selections.c.synced == 0).order_by(selections.c.seq_id).limit(limit)
        ).mappings().all()
    if not rows:
        return {"synced": 0, "pending": 0, "error": None}
    try:
        client.write_rows([(r["seq_id"] + 1, row_values(r)) for r in rows])
    except Exception as exc:  # network, quota, permissions...
        msg = str(exc)[:500]
        with engine.begin() as conn:
            conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                         .values(sync_error=msg))
        return {"synced": 0, "pending": len(rows), "error": msg}
    with engine.begin() as conn:
        conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                     .values(synced=1, sync_error=None))
    return {"synced": len(rows), "pending": 0, "error": None}
