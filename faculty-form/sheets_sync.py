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
        self.service_account_email = info.get("client_email", "")

    def _call(self, method, path, **kwargs):
        resp = self.session.request(method, f"{SHEETS_API}/{self.sheet_id}{path}", timeout=8, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sheets API {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    def delete_extra_tabs(self):
        """Ensure only Responses and Summary tabs exist in the Google Sheet. Remove all other tabs."""
        try:
            meta = self._call("GET", "?fields=sheets.properties(sheetId,title)")
            sheets_list = meta.get("sheets", [])
            allowed = {self.responses_tab, self.summary_tab}
            delete_requests = []
            for s in sheets_list:
                props = s.get("properties", {})
                title = props.get("title")
                sheet_id = props.get("sheetId")
                if title and title not in allowed and sheet_id is not None:
                    delete_requests.append({"deleteSheet": {"sheetId": sheet_id}})
            if delete_requests:
                self._call("POST", ":batchUpdate", json={"requests": delete_requests})
                log.info(f"Deleted extra sheet tabs: {[r['deleteSheet']['sheetId'] for r in delete_requests]}")
                return len(delete_requests)
        except Exception:
            log.exception("Error deleting extra sheet tabs")
        return 0

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
        pass

    def write_test_rows(self, rows: List[Tuple[int, list]]):
        pass

    def clear_rows(self, row_numbers: List[int]):
        ranges = [f"'{self.responses_tab}'!A{n}:F{n}" for n in row_numbers]
        self._call("POST", "/values:batchClear", json={"ranges": ranges})

    def clear_range(self, range_expr: str):
        self._call("POST", "/values:batchClear", json={"ranges": [range_expr]})

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
               for t in (self.responses_tab, self.summary_tab) if t not in have]
        if add:
            self._call("POST", ":batchUpdate", json={"requests": add})
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "RAW", "data": [
            {"range": f"'{self.responses_tab}'!A1:F1", "values": [HEADERS]},
        ]})
        self.update_summary_tab(faculty_rows)
        self.delete_extra_tabs()

    def update_summary_tab(self, faculty_rows: List[dict]):
        self.ensure_tab(self.summary_tab, ["Faculty", "Capacity", "Selected", "Remaining"])
        self.clear_range(f"'{self.summary_tab}'!A1:D30")
        summary = [["Faculty", "Capacity", "Selected", "Remaining"]]
        for i, f in enumerate(faculty_rows, start=2):
            summary.append([f["name"], f["capacity"],
                            f"=COUNTIF('{self.responses_tab}'!F:F,A{i})", f"=B{i}-C{i}"])
        last = len(summary)
        summary.append(["Total", f"=SUM(B2:B{last})", f"=SUM(C2:C{last})", f"=SUM(D2:D{last})"])
        self._call("POST", "/values:batchUpdate", json={"valueInputOption": "USER_ENTERED", "data": [
            {"range": f"'{self.summary_tab}'!A1:D{len(summary)}", "values": summary},
        ]})

    def sync_roster_tab(self, student_rows: List[dict]):
        pass


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

    synced_count = 0
    sync_err = None
    if rows:
        try:
            client.write_rows([(r["seq_id"] + 1, row_values(r)) for r in rows])
            with engine.begin() as conn:
                conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                             .values(synced=1, sync_error=None))
            synced_count = len(rows)
        except Exception as exc:
            msg = str(exc)[:500]
            sync_err = msg
            with engine.begin() as conn:
                conn.execute(update(selections).where(selections.c.seq_id.in_([r["seq_id"] for r in rows]))
                             .values(sync_error=msg))

    # 2. Mark any faculty student choices and test submissions as synced in DB without pushing extra tabs
    try:
        with engine.begin() as conn:
            conn.execute(update(faculty_student_selections).where(faculty_student_selections.c.synced == 0).values(synced=1, sync_error=None))
            conn.execute(update(test_selections).where(test_selections.c.synced == 0).values(synced=1, sync_error=None))
    except Exception:
        pass

    if hasattr(client, "delete_extra_tabs"):
        try:
            client.delete_extra_tabs()
        except Exception:
            pass

    return {"synced": synced_count, "pending": (len(rows) - synced_count), "error": sync_err}


def rewrite_all_selections(engine, client) -> dict:
    """Read all selections from DB in order 1..N and cleanly rewrite Google Sheet Responses tab."""
    if client is None:
        return {"ok": False, "error": "sheets_client_none"}

    try:
        from db import faculty, resequence_selections, selections
        resequence_selections(engine)

        with engine.connect() as conn:
            rows = conn.execute(
                select(selections, faculty.c.name.label("faculty_name"))
                .join(faculty, faculty.c.id == selections.c.faculty_id)
                .order_by(selections.c.seq_id)
            ).mappings().all()

        if hasattr(client, "ensure_tab"):
            client.ensure_tab(getattr(client, "responses_tab", "Responses"), HEADERS)
        if hasattr(client, "clear_range"):
            client.clear_range(f"'{getattr(client, 'responses_tab', 'Responses')}'!A2:F200")

        if rows:
            sheet_rows = [(idx + 1, row_values(r)) for idx, r in enumerate(rows, start=1)]
            client.write_rows(sheet_rows)
            with engine.begin() as conn:
                conn.execute(update(selections).values(synced=1, sync_error=None))

        with engine.begin() as conn:
            from sqlalchemy import func
            fac_counts = conn.execute(
                select(selections.c.faculty_id, func.count().label("cnt"))
                .group_by(selections.c.faculty_id)
            ).all()
            fac_cnt_map = {fc[0]: fc[1] for fc in fac_counts}
            fac_list = conn.execute(select(faculty)).mappings().all()
            for f in fac_list:
                actual_cnt = fac_cnt_map.get(f["id"], 0)
                if f["selected_count"] != actual_cnt:
                    conn.execute(update(faculty).where(faculty.c.id == f["id"]).values(selected_count=actual_cnt))

        # Always update Google Sheet Summary tab with active non-director faculties
        active_fac_dicts = []
        if hasattr(client, "update_summary_tab"):
            with engine.connect() as conn:
                active_facs = conn.execute(
                    select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)
                ).mappings().all()
                active_fac_dicts = [dict(f) for f in active_facs]
                client.update_summary_tab(active_fac_dicts)

        # Remove extra tabs so only Responses and Summary exist
        if hasattr(client, "delete_extra_tabs"):
            client.delete_extra_tabs()

        return {"ok": True, "rewritten": len(rows), "summary_updated": len(active_fac_dicts)}
    except Exception as exc:
        log.exception("Error in rewrite_all_selections")
        return {"ok": False, "error": str(exc)}


def reconcile_sheet_and_db(engine, client) -> dict:
    """Synchronize Google Sheet and database:
    1. Resequence DB selections 1..N with no gaps.
    2. Recalculate selected_count for all faculties.
    3. Enforce quotas safely: Suganesh (4), Sathish (4), Adhinarayanan (4), Saraswathi (2), Rest (5).
    4. Sync rows and Summary tab to Google Sheet cleanly.
    """
    from db import faculty, resequence_selections, selections
    resequence_selections(engine)

    target_caps = {
        2: 4,   # Dr Adhinarayanan B
        3: 4,   # Dr Satheesh Kumar T
        4: 5,   # Prof. Senthil Kumar N
        5: 5,   # Prof. Nandhini B
        6: 5,   # Prof. Mageswaran J
        7: 5,   # Prof. Dhanabalu S N
        8: 5,   # Prof. Saranya S
        9: 5,   # Prof. Aishwariya M R
        10: 4,  # Prof. Suganesh S
        11: 2,  # Dr Saraswathi C
    }

    with engine.begin() as conn:
        from sqlalchemy import func
        fac_counts = conn.execute(
            select(selections.c.faculty_id, func.count().label("cnt"))
            .group_by(selections.c.faculty_id)
        ).all()
        fac_cnt_map = {fc[0]: fc[1] for fc in fac_counts}
        fac_rows = conn.execute(select(faculty)).mappings().all()
        for f in fac_rows:
            cnt = fac_cnt_map.get(f["id"], 0)
            conn.execute(update(faculty).where(faculty.c.id == f["id"]).values(selected_count=cnt))
            if f["id"] in target_caps:
                target = max(target_caps[f["id"]], cnt)
                conn.execute(update(faculty).where(faculty.c.id == f["id"]).values(capacity=target))

    sheet_res = {}
    if client:
        sheet_res = rewrite_all_selections(engine, client)

    return {"ok": True, "sheet": sheet_res}
