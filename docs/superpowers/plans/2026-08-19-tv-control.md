# Studio Automation — Increment 7a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `control_tv` tool giving JARVIS direct control (power, volume, mute, app launching) over three TVs on three different platforms — TCL/Roku, Samsung/Tizen, LG/webOS — no Home Assistant, per the client's explicit direction to build studio automation directly into JARVIS.

**Architecture:** One dispatch tool (`_tool_control_tv`) routes to one small per-brand function each. Roku is plain stdlib `urllib` (its ECP has no auth). Samsung uses `samsungtvws` (built-in file-based token persistence). LG uses `PyWebOSTV` (persistence handled ourselves via a small local JSON file, since that library leaves storage to the caller). All three need Wake-on-LAN for power-on — verified during research that none of the three device control APIs are reachable once the TV is in deep sleep, so a UDP magic-packet broadcast (pure stdlib `socket`) is the only way to wake any of them remotely.

**Tech Stack:** FastAPI, stdlib `urllib`/`socket`/`json`, `samsungtvws` (new), `pywebostv` (new), pytest.

**Note on git:** the user handles all git init/commit/push themselves. No task in this plan runs a git command — each ends with a test/manual-verification step instead.

---

### Task 1: Configuration and dependencies

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add the six new TV settings**

Modify `backend/app/config.py`, replacing the `Settings` dataclass to add six new fields at the end (after `finnhub_api_key: str`):
```python
    finnhub_api_key: str
    tcl_tv_ip: str
    tcl_tv_mac: str
    samsung_tv_ip: str
    samsung_tv_mac: str
    lg_tv_ip: str
    lg_tv_mac: str
    database_path: Path
```

- [ ] **Step 2: Populate them in `get_settings`**

Modify `backend/app/config.py`, adding six new lines to the `return Settings(...)` call, right after `finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),`:
```python
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
        tcl_tv_ip=os.getenv("TCL_TV_IP", ""),
        tcl_tv_mac=os.getenv("TCL_TV_MAC", ""),
        samsung_tv_ip=os.getenv("SAMSUNG_TV_IP", ""),
        samsung_tv_mac=os.getenv("SAMSUNG_TV_MAC", ""),
        lg_tv_ip=os.getenv("LG_TV_IP", ""),
        lg_tv_mac=os.getenv("LG_TV_MAC", ""),
        database_path=DATA_DIR / "jarvis.db",
```

- [ ] **Step 3: Add the new dependencies**

Modify `backend/requirements.txt`, appending:
```
samsungtvws>=2.7.0
pywebostv>=0.8.9
```

- [ ] **Step 4: Add the env variables**

Modify `backend/.env`, appending:
```

# TV control (direct integration, no Home Assistant) — see Task 1 for setup
TCL_TV_IP=
TCL_TV_MAC=
SAMSUNG_TV_IP=
SAMSUNG_TV_MAC=
LG_TV_IP=
LG_TV_MAC=
```
Leave blank until the client provides these.

Modify `backend/.env.example`, appending the same block, also left blank.

- [ ] **Step 5: Install dependencies and verify settings load**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "import samsungtvws, pywebostv; print('ok')"
python -c "from app.config import get_settings; s = get_settings(); print(s.tcl_tv_ip, s.samsung_tv_ip, s.lg_tv_ip)"
```
Expected: `ok`, then three empty strings (blank until the client's details arrive).

---

### Task 2: Wake-on-LAN helper (TDD)

**Files:**
- Modify: `backend/tests/test_tools.py` (append tests)
- Modify: `backend/app/ai/tools.py` (imports, add `_build_magic_packet`, `_send_wake_on_lan`)

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/test_tools.py`, appending to the end of the file:
```python


def test_build_magic_packet_has_correct_length_and_prefix():
    from app.ai.tools import _build_magic_packet

    packet = _build_magic_packet("AA:BB:CC:DD:EE:FF")

    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6


def test_build_magic_packet_repeats_mac_sixteen_times():
    from app.ai.tools import _build_magic_packet

    packet = _build_magic_packet("AA:BB:CC:DD:EE:FF")
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")

    assert packet[6:] == mac_bytes * 16


def test_build_magic_packet_handles_hyphen_separated_mac():
    from app.ai.tools import _build_magic_packet

    packet_colon = _build_magic_packet("AA:BB:CC:DD:EE:FF")
    packet_hyphen = _build_magic_packet("AA-BB-CC-DD-EE-FF")

    assert packet_colon == packet_hyphen
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/test_tools.py -v
```
Expected: `ImportError: cannot import name '_build_magic_packet' from 'app.ai.tools'` on the 3 new tests.

- [ ] **Step 3: Add `socket` and `DATA_DIR` imports**

Modify `backend/app/ai/tools.py`, replacing the top import block:
```python
from __future__ import annotations

import io
import json
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import DATA_DIR, Settings, get_settings
from app.services import google_auth
from app.services.memory import MemoryStore
```

- [ ] **Step 4: Add `_build_magic_packet` and `_send_wake_on_lan`**

Modify `backend/app/ai/tools.py`, inserting right before `_tool_delete_task` begins (find it by searching for `def _tool_delete_task`) — this is the natural start of the new TV-control section, placed after the existing task tools and before `_normalize_url`:
```python
def _build_magic_packet(mac: str) -> bytes:
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    return b"\xff" * 6 + mac_bytes * 16


def _send_wake_on_lan(mac: str) -> None:
    packet = _build_magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, ("255.255.255.255", 9))


```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 73 passed (70 from before + 3 new).

---

### Task 3: Per-brand TV control functions

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_control_roku_tv`, `_control_samsung_tv`, `_load_lg_store`/`_save_lg_store`/`_control_lg_tv`)

- [ ] **Step 1: Add the Roku control function**

Modify `backend/app/ai/tools.py`, inserting right after `_send_wake_on_lan` ends (from Task 2):
```python
_ROKU_KEYS = {
    "power_off": "PowerOff",
    "volume_up": "VolumeUp",
    "volume_down": "VolumeDown",
    "mute": "VolumeMute",
}


def _control_roku_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the TCL TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the TCL TV."}

    if action == "launch_app":
        if not value:
            return {"error": "Which app should I launch on the TCL TV? (Roku needs a numeric app ID.)"}
        url = f"http://{ip}:8060/launch/{urllib.parse.quote(value)}"
    else:
        key = _ROKU_KEYS.get(action)
        if not key:
            return {"error": f"Unsupported action '{action}' for the TCL TV."}
        url = f"http://{ip}:8060/keypress/{key}"

    try:
        request = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(request, timeout=10):
            pass
    except Exception as exc:
        return {"error": f"Couldn't reach the TCL TV: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the TCL TV."}


```

- [ ] **Step 2: Add the Samsung control function**

Modify `backend/app/ai/tools.py`, inserting right after `_control_roku_tv` ends:
```python
def _control_samsung_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the Samsung TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the Samsung TV."}

    from samsungtvws import SamsungTVWS

    tv = SamsungTVWS(host=ip, token_file=str(DATA_DIR / "samsung_tv_token.txt"))

    try:
        if action == "power_off":
            tv.send_key("KEY_POWER")
        elif action == "volume_up":
            tv.send_key("KEY_VOLUP")
        elif action == "volume_down":
            tv.send_key("KEY_VOLDOWN")
        elif action == "mute":
            tv.send_key("KEY_MUTE")
        elif action == "launch_app":
            if not value:
                return {"error": "Which app should I launch on the Samsung TV?"}
            apps = tv.app_list() or []
            matches = [a for a in apps if value.lower() in str(a.get("name", "")).lower()]
            if not matches:
                return {"error": f"Couldn't find an app matching '{value}' on the Samsung TV."}
            tv.run_app(matches[0]["appId"])
        else:
            return {"error": f"Unsupported action '{action}' for the Samsung TV."}
    except Exception as exc:
        return {"error": f"Samsung TV command failed: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the Samsung TV."}


```

- [ ] **Step 3: Add the LG control function**

Modify `backend/app/ai/tools.py`, inserting right after `_control_samsung_tv` ends:
```python
def _load_lg_store() -> dict[str, Any]:
    store_path = DATA_DIR / "lg_tv_store.json"
    if store_path.exists():
        try:
            return json.loads(store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_lg_store(store_data: dict[str, Any]) -> None:
    store_path = DATA_DIR / "lg_tv_store.json"
    store_path.write_text(json.dumps(store_data), encoding="utf-8")


def _control_lg_tv(ip: str, mac: str, action: str, value: str) -> dict[str, Any]:
    if action == "power_on":
        if not mac:
            return {"error": "Can't power on the LG TV — no MAC address configured for Wake-on-LAN."}
        _send_wake_on_lan(mac)
        return {"message": "Sent a wake signal to the LG TV."}

    from pywebostv.connection import WebOSClient
    from pywebostv.controls import ApplicationControl, MediaControl, SystemControl

    client = WebOSClient(ip)
    try:
        client.connect()
    except Exception as exc:
        return {"error": f"Couldn't connect to the LG TV: {exc}"}

    store_data = _load_lg_store()
    try:
        for _status in client.register(store_data):
            pass
    except Exception as exc:
        return {"error": f"LG TV pairing failed: {exc}"}
    _save_lg_store(store_data)

    try:
        if action == "power_off":
            SystemControl(client).power_off()
        elif action == "volume_up":
            MediaControl(client).volume_up()
        elif action == "volume_down":
            MediaControl(client).volume_down()
        elif action == "mute":
            MediaControl(client).mute(True)
        elif action == "launch_app":
            if not value:
                return {"error": "Which app should I launch on the LG TV?"}
            app_control = ApplicationControl(client)
            apps = app_control.list_apps() or []
            matches = [a for a in apps if value.lower() in str(a.get("title", "")).lower()]
            if not matches:
                return {"error": f"Couldn't find an app matching '{value}' on the LG TV."}
            app_control.launch(matches[0])
        else:
            return {"error": f"Unsupported action '{action}' for the LG TV."}
    except Exception as exc:
        return {"error": f"LG TV command failed: {exc}"}

    return {"message": f"Done — {action.replace('_', ' ')} on the LG TV."}


```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 73 passed, no regressions (no new tests in this task — these three functions wrap real network/hardware calls, consistent with this project's established convention of not unit-testing network-calling code).

---

### Task 4: `control_tv` dispatch tool

**Files:**
- Modify: `backend/app/ai/tools.py` (add `_tool_control_tv`, `TOOL_DEFINITIONS` entry, `TOOL_REGISTRY` entry)

- [ ] **Step 1: Add the dispatch tool**

Modify `backend/app/ai/tools.py`, inserting right after `_control_lg_tv` ends (from Task 3) and before `_tool_delete_task` begins:
```python
def _tool_control_tv(args: dict[str, Any], user_id: str, store: MemoryStore) -> dict[str, Any]:
    tv = str(args.get("tv", "")).strip().lower()
    action = str(args.get("action", "")).strip().lower()
    value = str(args.get("value") or "").strip()

    if tv not in {"tcl", "samsung", "lg"}:
        raise ValueError("tv must be one of: tcl, samsung, lg.")
    if not action:
        raise ValueError("An action is required.")

    settings = get_settings()
    tv_config = {
        "tcl": (settings.tcl_tv_ip, settings.tcl_tv_mac, _control_roku_tv),
        "samsung": (settings.samsung_tv_ip, settings.samsung_tv_mac, _control_samsung_tv),
        "lg": (settings.lg_tv_ip, settings.lg_tv_mac, _control_lg_tv),
    }
    ip, mac, control_fn = tv_config[tv]
    if not ip:
        return {"error": f"The {tv} TV isn't configured yet — no IP address set."}

    return control_fn(ip, mac, action, value)


```

- [ ] **Step 2: Add the `TOOL_DEFINITIONS` entry**

Modify `backend/app/ai/tools.py`, inserting a new entry right before the closing `]` of `TOOL_DEFINITIONS` (find it by searching for the `delete_task` entry's closing `},\n    },\n]`), i.e. right after `delete_task`'s entry and before the list's closing bracket:
```python
    {
        "type": "function",
        "function": {
            "name": "control_tv",
            "description": "Control a TV — power, volume, mute, or launch an app. For Samsung/LG, value for launch_app is an app name (fuzzy matched). For tcl (Roku), value must be a numeric Roku app ID, not a name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tv": {"type": "string", "description": "Which TV: tcl, samsung, or lg."},
                    "action": {
                        "type": "string",
                        "description": "power_on, power_off, volume_up, volume_down, mute, or launch_app.",
                    },
                    "value": {
                        "type": ["string", "null"],
                        "description": "App name/ID, only used with launch_app.",
                    },
                },
                "required": ["tv", "action"],
            },
        },
    },
```

- [ ] **Step 3: Register the tool**

Modify `backend/app/ai/tools.py`, adding a line to `TOOL_REGISTRY`, right after `"propose_delete_calendar_event": _tool_propose_delete_calendar_event,`:
```python
    "control_tv": _tool_control_tv,
```

- [ ] **Step 4: Run the tests**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 73 passed, no regressions. Confirm the token-budget regression guards in `test_provider.py` still pass — if either fails, trim the new tool's description rather than raising the ceiling.

---

### Task 5: System prompt

**Files:**
- Modify: `backend/app/ai/provider.py` (`SYSTEM_PROMPT` tool bullet + new rule)

- [ ] **Step 1: Add the tool bullet**

Modify `backend/app/ai/provider.py`, inserting a new line at the end of the tool bullet list (find the last bullet, currently `list_calendar_events / draft_calendar_event / propose_delete_calendar_event`, and insert right after it):
```python
• control_tv — power/volume/mute/launch an app on the tcl, samsung, or lg TV; no confirmation needed, these are local reversible actions
```

- [ ] **Step 2: Add a new rule**

Modify `backend/app/ai/provider.py`, inserting a new rule right before the final personality rule (find the highest-numbered rule — currently the "Be warm and professional..." rule — and insert a new rule just before it, renumbering that rule up by one):
```python
{N}. When the user names a TV (or it's clear from context which one) and asks to turn it on/off, change volume, mute, or open an app, call control_tv directly — never just describe the action in text, that gives the user nothing actually happening (same principle as request_file_upload). If the TV they mean is ambiguous with more than one in play, ask which one.
```
Replace `{N}` with the correct next rule number, and renumber the final personality rule to `{N+1}`.

- [ ] **Step 3: Run the full test suite**

Run:
```powershell
cd "C:\Anchal\Fiverr\Ultimate JARVIS\backend"
python -m pytest tests/ -v
```
Expected: 73 passed, no regressions. Confirm the token-budget regression guards still pass — if either fails, trim the new bullet/rule text rather than raising the ceiling (matching how this was handled for `detect_highlights` in 6e).

---

### Task 6: End-to-end manual verification

**Files:** None (verification only).

- [ ] **Step 1: Restart the backend**

Run (PowerShell):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
  $procId = $_
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\Anchal\Fiverr\Ultimate JARVIS\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 4
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Expected: `{"status":"online","service":"jarvis-backend"}`. If any PowerShell command hangs unexpectedly, fall back to starting the server directly via a bash-compatible shell rather than waiting indefinitely.

- [ ] **Step 2: Configuration-not-set path (works immediately, no client details needed yet)**

Ask JARVIS to turn on the Samsung TV before any IPs are configured. Expected: a clear "not configured yet" message, not a crash. This step can be done right away, before the client sends any TV details.

- [ ] **Step 3: Once the client provides TV IPs/MACs**

Populate `.env` with the real values and restart the backend. Confirm the standby-wake setting (`Fast TV Start` / `Quick Start` / equivalent) is enabled on each physical TV first.

- [ ] **Step 4: Power on/off**

Ask JARVIS to turn off, then on, each TV by name. Confirm real responses, including power-on from fully off via Wake-on-LAN for all three.

- [ ] **Step 5: Pairing prompts**

For Samsung and LG, confirm the one-time on-screen pairing prompt appears on first use, and that subsequent calls don't re-prompt (persisted token/store working correctly).

- [ ] **Step 6: Volume/mute**

Ask for volume up/down and mute on each TV. Confirm real, audible/visible changes.

- [ ] **Step 7: App launching**

Ask to launch an app by name on the Samsung and LG TVs (e.g. "open Netflix on the LG"). Confirm the app actually opens. For the TCL, confirm the tool correctly asks for/expects a numeric app ID rather than silently failing on a name.

- [ ] **Step 8: Ambiguity handling**

Ask JARVIS to control "the TV" without naming a specific one, when more than one has been discussed recently. Confirm it asks for clarification rather than guessing.

- [ ] **Step 9: Voice-safe replies**

Confirm every reply stays voice-safe (plain spoken confirmation, no tool syntax leaking through).

- [ ] **Step 10: Stop the backend**

Ctrl+C in its terminal (leave the frontend running if continuing to use it).

---

### Task 7: Update the testing guide

**Files:**
- Modify: `docs/testing-guide.md`

- [ ] **Step 1: Append a new section**

Modify `docs/testing-guide.md`, inserting a new "TV Control" section right before the closing `## Adding a new feature?` section, following the same format as the existing sections (feature description sentence, then numbered steps), grounded in Task 6's manual verification steps above. Note explicitly that this is the first Studio Automation feature and doesn't depend on Home Assistant.

---

## Post-plan: what's explicitly not in this increment

- Lights (smart relay for power-only; direct Tuya integration for the flush-mount light).
- Cameras (HIKvision, Fomako).
- Other Section 2 hardware (smart plugs, AC, monitors, projectors, Stream Deck, NAS, UPS).
- Auto-discovery of TVs on the network.
- Multi-device "scene" automation (e.g. "Podcast Mode").
