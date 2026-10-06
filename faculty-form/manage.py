"""Organiser tools (run from your computer, pointing at the same DATABASE_URL as the live app).

  python manage.py init-db            create tables and load faculty.csv + roster.csv
  python manage.py status             seats per faculty
  python manage.py list               every selection, in FCFS order
  python manage.py reset <reg|email>  free a student's seat (they can choose again)
  python manage.py sync               push any unsynced selections to the Google Sheet
  python manage.py init-sheet         create Responses/Summary tabs with headers and formulas
  python manage.py export out.csv     save all selections to a CSV file
"""
import csv
import sys

import allocation
import config
import db
import sheets_sync
from sqlalchemy import select


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    settings = config.load_settings()
    engine = db.make_engine(settings.database_url)
    db.init_schema(engine)

    if cmd == "init-db":
        changed = db.seed(engine, force=True)
        print("Database ready." if changed is not None else "Nothing to do.")
        print_status(engine)
    elif cmd == "status":
        db.seed(engine)
        print_status(engine)
    elif cmd == "list":
        with engine.connect() as conn:
            rows = conn.execute(
                select(db.selections, db.faculty.c.name.label("fac"))
                .join(db.faculty, db.faculty.c.id == db.selections.c.faculty_id)
                .order_by(db.selections.c.seq_id)).mappings().all()
        for r in rows:
            print(f"{r['seq_id']:>3}  {config.fmt_ist(r['created_ms'])}  {r['register_no']}  "
                  f"{r['student_name']:<26} {r['fac']}  {'synced' if r['synced'] else 'NOT SYNCED'}")
        print(f"{len(rows)} selection(s)")
    elif cmd == "reset":
        if len(argv) < 3:
            print("Usage: python manage.py reset <register_no or email>")
            return 1
        removed = allocation.reset_student(engine, argv[2])
        if removed is None:
            print("No selection found for that student.")
            return 1
        print(f"Seat freed for {removed['student_name']} ({removed['register_no']}).")
        client = sheets_sync.get_client(settings)
        if client:
            client.clear_rows([removed["seq_id"] + 1])
            print("Sheet row cleared.")
        else:
            print("Sheet not configured: clear that row in the Responses tab by hand.")
    elif cmd == "sync":
        client = sheets_sync.get_client(settings)
        print(sheets_sync.sync_pending(engine, client, limit=1000))
    elif cmd == "init-sheet":
        client = sheets_sync.get_client(settings)
        if client is None:
            print("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE first.")
            return 1
        db.seed(engine)
        client.init_layout([dict(r) for r in allocation.availability(engine)])
        print(f"Sheet ready. Share it as Editor with: {client.service_account_email}")
    elif cmd == "export":
        path = argv[2] if len(argv) > 2 else "selections.csv"
        with engine.connect() as conn:
            rows = conn.execute(
                select(db.selections, db.faculty.c.name.label("fac"))
                .join(db.faculty, db.faculty.c.id == db.selections.c.faculty_id)
                .order_by(db.selections.c.seq_id)).mappings().all()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(sheets_sync.HEADERS)
            for r in rows:
                w.writerow([r["seq_id"], config.fmt_ist(r["created_ms"]), r["student_name"],
                            r["register_no"], r["email"], r["fac"]])
        print(f"Wrote {len(rows)} rows to {path}")
    else:
        print(__doc__)
        return 1
    return 0


def print_status(engine):
    print(f"{'Faculty':<26}{'Capacity':>9}{'Selected':>9}{'Remaining':>10}")
    total = [0, 0]
    with engine.connect() as conn:
        for r in conn.execute(select(db.faculty).order_by(db.faculty.c.id)).mappings():
            print(f"{r['name']:<26}{r['capacity']:>9}{r['selected_count']:>9}{r['capacity'] - r['selected_count']:>10}")
            total[0] += r["capacity"]
            total[1] += r["selected_count"]
    print(f"{'Total':<26}{total[0]:>9}{total[1]:>9}{total[0] - total[1]:>10}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
