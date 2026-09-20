"""Generate a JARVIS_PASSWORD_HASH line to paste into backend/.env.

Run from the backend/ directory: python scripts/set_password.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.auth import hash_password  # noqa: E402


def main() -> None:
    password = getpass.getpass("New JARVIS login password: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords didn't match. Nothing changed.")
        return
    if len(password) < 8:
        print("Use at least 8 characters.")
        return

    print("\nAdd this line to backend/.env (replacing any existing JARVIS_PASSWORD_HASH):\n")
    print(f"JARVIS_PASSWORD_HASH={hash_password(password)}")


if __name__ == "__main__":
    main()
