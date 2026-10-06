import allocation
import sheets_sync
from helpers import T0, counts, start_and_claim


def test_rows_land_at_seq_plus_one_in_fcfs_order(engine, students, sheets):
    for i, s in enumerate(students[:4]):
        assert start_and_claim(engine, s, 1 + i, T0 + i * 1000).ok
    out = sheets_sync.sync_pending(engine, sheets)
    assert out == {"synced": 4, "pending": 0, "error": None}
    assert sorted(sheets.rows) == [2, 3, 4, 5]
    assert [sheets.rows[n][2] for n in (2, 3, 4, 5)] == [s["name"] for s in students[:4]]
    assert sheets.rows[2][:1] == [1] and len(sheets.rows[2]) == 6


def test_sheet_outage_never_loses_or_blocks_a_selection(engine, students, sheets):
    sheets.fail = True
    assert start_and_claim(engine, students[0], 1).ok          # seat is still granted
    out = sheets_sync.sync_pending(engine, sheets)
    assert out["synced"] == 0 and "sheets down" in out["error"]
    fac, n = counts(engine)
    assert n == 1 and fac[1][0] == 1 and sheets.rows == {}

    assert start_and_claim(engine, students[1], 2).ok          # next student also fine during the outage
    sheets.fail = False
    out = sheets_sync.sync_pending(engine, sheets)             # recovery pushes everything, in order
    assert out["synced"] == 2 and sorted(sheets.rows) == [2, 3]


def test_retrying_never_duplicates_rows(engine, students, sheets):
    assert start_and_claim(engine, students[0], 1).ok
    sheets_sync.sync_pending(engine, sheets)
    # simulate "synced flag lost" (e.g. crash after the write): the same row is simply rewritten
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("UPDATE selections SET synced = 0"))
    sheets_sync.sync_pending(engine, sheets)
    assert len(sheets.rows) == 1 and 2 in sheets.rows


def test_nothing_to_do_and_no_client(engine, students, sheets):
    assert sheets_sync.sync_pending(engine, sheets)["pending"] == 0
    assert start_and_claim(engine, students[0], 1).ok
    out = sheets_sync.sync_pending(engine, None)
    assert out["error"] == "sheets_not_configured"
    assert counts(engine)[1] == 1                               # selection unaffected


def test_reset_clears_the_sheet_row_position(engine, students, sheets):
    assert start_and_claim(engine, students[0], 1).ok
    sheets_sync.sync_pending(engine, sheets)
    removed = allocation.reset_student(engine, students[0]["email"])
    sheets.clear_rows([removed["seq_id"] + 1])
    assert sheets.rows == {}
