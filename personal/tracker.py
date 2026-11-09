#!/usr/bin/env python3
"""Import historical applications locally, without fetching any employer URL."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIRMED = re.compile(r"^(submitted(?: successfully| by email)?(?:;|$)|application sent by email;)", re.I)
NEGATIVE = re.compile(r"not submitted|unconfirmed|pending.*submission|failed|rejected by employer server", re.I)

def normalize(data):
    confirmed, pending = [], []
    seen = set()
    for item in data.get("applications", []):
        status = str(item.get("status", ""))
        row = {"company": item.get("company", ""), "title": item.get("role", ""),
               "url": item.get("url", ""), "location": item.get("country", ""),
               "source_status": status, "applied_at": item.get("submitted_date"),
               "confirmation": item.get("confirmation", "")}
        if not row["url"] or not row["company"] or not row["title"]:
            pending.append(row)
            continue
        key = (row["company"].casefold(), row["title"].casefold(), row["url"].rstrip("/"))
        if key in seen:
            continue
        seen.add(key)
        if CONFIRMED.search(status) and not NEGATIVE.search(status):
            confirmed.append(row)
        else:
            pending.append(row)
    return confirmed, pending

def apply(rows):
    # Called only after loading this install's local database URL.
    from backend.models.db import SessionLocal, Job, Application, utcnow
    from backend.accounts.context import use_account, owner_id_for_session
    from backend.scraper._shared.dedup import make_external_id
    from backend.accounts.settings import put_setting
    added = skipped = 0
    with SessionLocal() as db:
        owner = owner_id_for_session(db)
        if owner is None:
            raise SystemExit("Start the app once to create its owner account first.")
        with use_account(owner):
            for row in rows:
                external = make_external_id(row["company"], row["title"], row["url"])
                job = db.query(Job).filter(Job.external_id == external).first()
                if job and db.query(Application).filter(Application.job_id == job.id).first():
                    skipped += 1
                    continue
                if job is None:
                    job = Job(external_id=external, company=row["company"], title=row["title"],
                              url=row["url"], location=row["location"], source="personal_tracker",
                              status="applied", seen=True)
                    db.add(job)
                    db.flush()
                job.status = "applied"
                stamp = utcnow()
                if row["applied_at"]:
                    try:
                        stamp = datetime.fromisoformat(str(row["applied_at"]).replace("Z", "+00:00"))
                        if stamp.tzinfo is None:
                            stamp = stamp.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                db.add(Application(job_id=job.id, status="applied", applied_at=stamp,
                                   notes="Imported from existing tracker; no new submission. " + row["source_status"],
                                   status_transitions=[{"from": None, "to": "applied", "at": stamp.isoformat(),
                                                        "source": "personal_tracker_import"}]))
                added += 1
            # No billable fallback is configured by this setup.
            put_setting(db, "llm_provider", "codex_cli")
            put_setting(db, "llm_model", "")
            put_setting(db, "llm_fallback_provider", "")
            put_setting(db, "llm_fallback_model", "")
            db.commit()
    return added, skipped

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tracker", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write confirmed applications to the LOCAL database")
    args = parser.parse_args()
    confirmed, pending = normalize(json.loads(args.tracker.read_text()))
    from personal.manage import STATE, environment
    env = environment()
    os.environ.update(env)
    output = STATE / "tracker-import.json"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"confirmed": confirmed, "pending": pending}, f, indent=2)
    print(f"Confirmed historical applications: {len(confirmed)}; other records preserved locally: {len(pending)}")
    if args.apply:
        added, skipped = apply(confirmed)
        print(f"Imported: {added}; already present: {skipped}. No employer requests made.")
    else:
        print("Preview only. Add --apply to import into this local database.")
