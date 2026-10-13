"""Reset the working database back to the original.

Usage (from the hw5 folder):  python scripts/reset_db.py
Overwrites data/campus_customs_new.db with a fresh copy of data/campus_customs.db.
The original file is only ever read, never modified.
"""
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, ORIGINAL_DB  # noqa: E402

if not ORIGINAL_DB.exists():
    sys.exit(f"Original database not found at {ORIGINAL_DB}")

shutil.copyfile(ORIGINAL_DB, DB_PATH)
DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
print(f"Reset {DB_PATH.name} from {ORIGINAL_DB.name}")
