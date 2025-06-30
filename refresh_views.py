from sqlalchemy import text
from db import _engine      # same helper you already have

VIEWS = [
    "analysis.mv_track_projection",
    "analysis.mv_stint_summary",
    "analysis.mv_pit_stop_timeline",
    "analysis.mv_sector_performance",
    "analysis.mv_driver_summary_season",
]

def refresh(view: str):
    if view not in VIEWS:
        raise ValueError("Unknown view")
    with _engine().connect() as con:
        con.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};"))

def refresh_all():
    for v in VIEWS:
        refresh(v)

if __name__ == "__main__":
    refresh_all()
