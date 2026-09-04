# Studio Automation — Increment 7a: TV Control

## Context

This begins Section 2 of `AGENT.md` (Studio Automation), previously blocked on a Home Assistant setup decision. Per the client's explicit direction, studio automation will be built as **direct integrations inside JARVIS**, not routed through a separate Home Assistant hub — trading more code now for full ownership (matching AGENT.md's "full source code" / "full ownership of the project" requirement) and one unified codebase instead of two systems to maintain.

TV control is the first sub-increment: three TVs (TCL/Roku, Samsung/Tizen, LG/webOS), each on a genuinely different, incompatible control protocol. Prior-art research confirmed real, usable options for all three:
- **Roku (TCL)**: the "External Control Protocol" (ECP) — a plain local HTTP API on port 8060, no login, no API key, no cloud dependency. Simple enough to hit directly with stdlib `urllib`, no new dependency.
- **Samsung (Tizen)**: [`samsungtvws`](https://github.com/xchwarze/samsung-tv-ws-api), the standard Python library for this, with both sync and async modes available.
- **LG (webOS)**: [`PyWebOSTV`](https://github.com/supersaiyanmode/PyWebOSTV), a synchronous library — chosen over the more commonly cited `aiowebostv` specifically because that one is async-only (built for Home Assistant's async architecture) and would be awkward to bridge into this project's plain synchronous tool functions.

- **7a (this increment)**: TV control (power, volume, mute, app/input launching) for all three TVs via one unified tool.
- **Later**: lights (smart relay for power-only control of GVM/Godox; direct integration for the Tuya-based flush-mount light), cameras (HIKvision via ONVIF/`python-onvif`, Fomako PTZ if applicable), other Section 2 hardware (smart plugs, AC, monitors, projectors, Stream Deck, NAS, UPS) as later sub-increments — each following the same "one library/protocol per device type, one JARVIS tool per device type" pattern established here.

## Scope

**In scope:**
1. A new `control_tv(tv, action, value)` tool covering all three TVs through one consistent interface.
2. Three new config settings (`TCL_TV_IP`, `SAMSUNG_TV_IP`, `LG_TV_IP`), following the exact `.env`/`config.py` pattern already used for every other integration in this project.
3. Two new dependencies: `samsungtvws`, `pywebostv` (the PyPI package name for PyWebOSTV) — both well-maintained, purpose-built libraries; writing raw Tizen/webOS protocol handling from scratch would be far more fragile and isn't justified when solid libraries already exist (same reasoning already applied to `beautifulsoup4`/`pypdf` elsewhere in this project).
4. Actions: power on, power off, volume up, volume down, mute/unmute, and app/input launching (e.g. opening a specific streaming app or input source) — the full "remote control" feature set, not just on/off.
5. Per-TV connection handling: Roku via plain HTTP (no pairing needed), Samsung via `samsungtvws` (first connection may require accepting a pairing prompt on the TV itself — documented in the manual verification plan), LG via `PyWebOSTV` (requires an initial pairing handshake, whose resulting client key needs to be stored for reuse — see Design).

**Out of scope:**
- Auto-discovery of TVs on the network (mDNS/SSDP) — IP addresses are provided directly by the client and stored in config, avoiding the complexity of building reliable discovery for three different protocols.
- Any other Section 2 device (lights, cameras, smart plugs, etc.) — later sub-increments.
- A scheduling/automation engine (e.g. "turn off TVs at midnight automatically without being asked") — Section 2's "Podcast Mode" style multi-device scenes are a later increment once individual device control exists across enough devices to compose them meaningfully.

## Design

### Tool: `control_tv`

`backend/app/ai/tools.py` gains `_tool_control_tv(args, user_id, store)`. Parameters:
- `tv` (string, required): `"tcl"`, `"samsung"`, or `"lg"`.
- `action` (string, required): `"power_on"`, `"power_off"`, `"volume_up"`, `"volume_down"`, `"mute"`, or `"launch_app"`.
- `value` (string, optional): the app/input name, only used when `action` is `"launch_app"`.

The function dispatches to one of three small per-brand helper functions based on `tv`, each translating the requested `action` into that brand's actual protocol calls. This is a direct-execution tool (no confirmation gate) — turning a TV on/off or adjusting volume is local, immediately visible, and trivially reversible, the same tier as `add_task`, not the send-email/calendar-write tier that requires a human click.

### Per-brand handling

**Roku (`_control_roku_tv`)**: plain HTTP calls to `http://<ip>:8060/keypress/<key>` for power-off/volume/mute (Roku's remote-key names: `PowerOff`, `VolumeUp`, `VolumeDown`, `VolumeMute`) and `http://<ip>:8060/launch/<app_id>` for app launching. No dependency beyond stdlib `urllib`. Verified this does **not** extend to powering on: once a Roku TV enters deep sleep, ECP itself becomes unreachable (there is no `PowerOn` key — confirmed via Roku's own community/developer docs), so power-on needs Wake-on-LAN here too, the same as Samsung and LG (see below), provided `Fast TV Start` is enabled on the TV.

**Samsung (`_control_samsung_tv`)**: uses `samsungtvws.SamsungTVWS(host=ip, token_file=<path>)` in sync mode — the library has built-in file-based token persistence via its `token_file` parameter, so no custom storage code is needed. Calls `.send_key("KEY_VOLUP"/"KEY_VOLDOWN"/"KEY_MUTE")` for volume/mute and `.run_app(app_id)` for launching (finding the right `app_id` via `.app_list()`). First-time connection requires the user to accept a one-time pairing prompt that appears on the TV screen — documented as a manual step, not something JARVIS can bypass (Samsung-enforced security, not a library limitation). Powering on from a fully-off state requires Wake-on-LAN (see below) since the TV's WebSocket API isn't reachable once its network stack is down.

**LG (`_control_lg_tv`)**: uses `PyWebOSTV`'s `WebOSClient(ip)`, which requires an initial pairing handshake (a prompt appears on the TV, the user accepts it once) that produces a reusable client key inside a `store` dict. Unlike `samsungtvws`, `PyWebOSTV` leaves persistence entirely to the caller — so this `store` is read from and written to a small local JSON file (`backend/data/lg_tv_store.json`), the same "small local file next to the SQLite database" pattern already used for uploads (`backend/data/uploads/`). Like Samsung, powering on from fully-off requires Wake-on-LAN.

**Wake-on-LAN for power-on (all three TVs)**: each TV's control API is unreachable once the TV is in deep sleep/fully powered down — networked communication itself is what enables the connection in the first place, so there's nothing to send a "power on" command *to* through the normal channel. The standard, correct fix (used by Home Assistant's own TV integrations, and Roku's own official Wake-on-LAN channel) is Wake-on-LAN: broadcasting a UDP "magic packet" containing the TV's MAC address, which the network card can still respond to in low-power standby. This requires each TV's standby-wake setting enabled (`Fast TV Start` for Roku, `Quick Start`/similar for Samsung, `Quick Start+`/similar for LG — a one-time TV setting, not something JARVIS controls) and each TV's MAC address stored in config. Implemented as one small, shared, stdlib-only `_send_wake_on_lan(mac)` helper (a UDP broadcast, no new dependency) used by all three brands.

### Configuration

`backend/app/config.py` gains `tcl_tv_ip: str`, `tcl_tv_mac: str`, `samsung_tv_ip: str`, `samsung_tv_mac: str`, `lg_tv_ip: str`, `lg_tv_mac: str`, read from `.env`, following the exact pattern already used for `tavily_api_key` etc. The MAC address settings are optional (only needed for `power_on`); if missing, `power_on` on that TV returns a clear "can't power on — no MAC address configured for Wake-on-LAN" message rather than silently failing. If a given TV's IP isn't configured at all, `control_tv` returns a clear "that TV isn't configured yet" message for that specific brand rather than failing opaquely or affecting the other two TVs.

### Tool definition

```
name: control_tv
description: "Control a TV (TCL/Roku, Samsung, or LG) — power, volume, mute, or launch an app/input."
parameters:
  tv: string, required — "tcl", "samsung", or "lg".
  action: string, required — "power_on", "power_off", "volume_up", "volume_down", "mute", or "launch_app".
  value: string, optional — app/input name, only used with launch_app.
```

### System prompt

A new tool bullet, and a short rule: when the user names a TV or says something like "turn on the samsung," "mute the tv," "turn off the tcl," resolve which TV they mean from context (explicit brand name, or the only TV mentioned recently) and call `control_tv` — never describe the action in plain text instead of calling the tool (same "never just describe it" principle already applied to `request_file_upload` after that exact bug surfaced in 6e).

### Testing

The per-brand `action`-to-protocol-command mapping (e.g. `"volume_up"` → Roku's `"VolumeUp"` keypress, or → Samsung's specific key constant) is pure logic and gets unit tests. The actual network calls to each TV (Roku HTTP, Samsung WebSocket, LG WebSocket) are not unit-tested, consistent with this project's established convention — verified manually instead, since they require real hardware on the network.

### Manual verification plan

1. Once the client provides all three TVs' IPs and MAC addresses, and confirms the standby-wake setting (`Fast TV Start` / `Quick Start` / equivalent) is enabled on each TV, populate `.env` and restart the backend.
2. Ask JARVIS to turn off, then on, each TV individually by name ("turn off the samsung tv," then "turn it back on"). Confirm the TV actually responds — including power-on from fully off via Wake-on-LAN, for all three. For Samsung and LG, confirm the one-time on-screen pairing prompt appears on first use and that subsequent calls don't re-prompt.
3. Ask for volume up/down and mute on each TV. Confirm real, audible/visible changes.
4. Ask to launch an app (e.g. "open Netflix on the LG") if the TV/library supports it. Confirm the app actually opens.
5. Try referencing a TV whose IP isn't configured yet. Confirm a clear "not configured" message, not a crash, and that it doesn't affect the other two TVs.
6. Try power-on on a TV with no MAC address configured. Confirm a clear "can't power on, no MAC configured" message, not a crash.
7. Ask JARVIS to control a TV without specifying which one, when only one has been discussed recently. Confirm it correctly infers which TV, or asks for clarification if genuinely ambiguous.
8. Confirm the reply stays voice-safe (plain spoken confirmation, no tool syntax leaking through).

## Explicitly deferred to future increments

- Lights (smart relay + direct Tuya integration).
- Cameras (HIKvision, Fomako).
- Other Section 2 hardware (smart plugs, AC, monitors, projectors, Stream Deck, NAS, UPS).
- Auto-discovery of TVs on the network.
- Multi-device "scene" automation (e.g. "Podcast Mode").
