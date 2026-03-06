# Sphero BOLT Multi-Agent STEM Expo Controller

This project controls multiple Sphero BOLT robots from a single Windows (or macOS) laptop over Bluetooth LE, runs decentralized zone-choice behavior, and logs repeatable CSV trial data.

## 1) Python Requirement (Exact)

- `Python 3.11.9` (required)

Why this exact version: it is a stable target for `bleak` + `spherov2` BLE stacks used here.

## 2) Project Layout

```text
sphero_stem_expo/
  README.md
  requirements.txt
  config.example.json
  config.json                  # created/updated by discovery script
  data/                        # CSV output
  scripts/
    run_discovery.py
    run_launcher.py
    run_mvp.py
    run_stop.py
    run_trial.py
  src/
    __init__.py
    agent.py
    config.py
    constants.py
    crowding.py
    discovery.py
    robot_client.py
    schedule.py
    sdk.py
    trial.py
    trial_logger.py
```

## 3) Install

### Windows (recommended for expo runtime)

```powershell
cd "C:\path\to\sphero_stem_expo"
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS

```bash
cd /path/to/sphero_stem_expo
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3.1) Optional: Launcher App (Easier Run Flow)

Start a local desktop launcher with buttons for scan, discovery save, MVP, trial, and emergency stop:

```bash
python scripts/run_launcher.py
```

Recommended launcher flow:
1. Click `Select Robots (GUI)`
2. Click `Scan Nearby`, select robots, then `Save Selection`
4. Click `Run MVP`
5. Click `Run Trial`

For manual lambda testing with inferred crowding, use:
- `Run Trial (lambda=2, inferred)`
- `Run Trial (lambda=6, inferred)`
- `Run Trial (lambda=10, inferred)`

Emergency control:
- Click `Emergency Stop` or `Interrupt`

## 4) Verify Bluetooth LE on Windows

1. Turn Bluetooth ON in Windows Settings.
2. In PowerShell, verify Bluetooth service/device:
   - `Get-Service bthserv`
   - `Get-PnpDevice -Class Bluetooth`
3. Run a BLE scan from this project:

```powershell
python scripts\run_discovery.py --list-only --timeout 10
```

If BOLT devices appear in the list, BLE discovery is working.

## 5) Discovery + Save Robot Config

Run discovery, then select robots by index, name, or BLE address:

```bash
python scripts/run_discovery.py --timeout 10
```

This writes `config.json` with selected robots.

Example `config.json`:

```json
{
  "robots": [
    {"name": "SB-4A12", "address": "C1:23:45:67:89:AB"},
    {"name": "SB-8F20", "address": "D2:34:56:78:9A:BC"},
    {"name": "SB-9150", "address": "E3:45:67:89:AB:CD"}
  ]
}
```

## 6) Run 3-Robot MVP Movement Test

Use this first to verify concurrent connect + roll + stop reliability:

```bash
python scripts/run_mvp.py --num-robots 3 --speed 60 --roll-seconds 2
```

Expected behavior:
- connects to 3 configured robots
- each robot rolls on heading patterns and stops
- clean disconnect at end

Emergency stop (any time):
```bash
python scripts/run_stop.py --num-robots 3
```

Also, pressing `Ctrl+C` during `run_mvp.py` or `run_trial.py` stops and disconnects robots.

## 7) Run a Trial (Decentralized Agents)

Arena assumptions encoded in code:
- zone headings from center start box:
  - `A=315`, `B=45`, `C=225`, `D=135`
- rotating value schedule:
  - `0-30s: A40 B30 C20 D10`
  - `30-60s: A10 B40 C30 D20`
  - `60-90s: A20 B10 C40 D30`
- score rule:
  - `score = zone_value(t) - (lambda * robots_near_zone)`

### Option A: inferred crowding (from last chosen zones)

```bash
python scripts/run_trial.py --num-robots 3 --lambda-value 2 --crowding-mode inferred
```

### Option B: manual crowding input

```bash
python scripts/run_trial.py --num-robots 3 --lambda-value 2 --crowding-mode manual
```

Manual mode accepts terminal updates like:
- `A:2 B:3 C:1 D:2`
- Update roughly every 10 seconds during the 90-second trial.

If no new input is provided, last valid crowding values remain active.

## 8) Scale from 3 -> 5 -> 8

1. Add/refresh selected robots in config:
   - `python scripts/run_discovery.py`
2. MVP at new scale:
   - `python scripts/run_mvp.py --num-robots 5`
   - `python scripts/run_mvp.py --num-robots 8`
3. Run trials:
   - `python scripts/run_trial.py --num-robots 5 --lambda-value 6 --crowding-mode inferred`
   - `python scripts/run_trial.py --num-robots 8 --lambda-value 10 --crowding-mode inferred`

Recommended ramp:
- 3 robots stable -> 5 robots stable -> 8 robots.

## 9) CSV Logging

Each trial writes one CSV in `data/`:

`trial_YYYYMMDD_HHMMSS_lambda{L}_n{N}_{mode}.csv`

Columns:
- `timestamp`
- `lambda`
- `segment` (`0-30`, `30-60`, `60-90`)
- `robot_id`
- `chosen_zone`
- `crowding_used` (e.g., `A:2 B:3 C:1 D:2`)

## 10) Troubleshooting (Disconnects / Pairing)

1. Robot not found in scan:
   - Wake each BOLT (tap/charge).
   - Keep robots within 1-3m during connection.
   - Disable other apps that may hold BOLT BLE sessions.
2. Frequent disconnects:
   - Reduce simultaneous connect pressure by reconnecting once, then starting trial.
   - Lower movement speed (e.g., `--speed 45`) during validation.
   - Keep laptop power profile on high performance and disable sleep.
3. Windows paired but cannot connect:
   - Remove BOLT from Windows Bluetooth paired devices.
   - Reboot Bluetooth service: `Restart-Service bthserv` (admin PowerShell).
   - Re-run `run_discovery.py` and select again.
4. Duplicate robot names:
   - Prefer unique BLE addresses in `config.json`.
   - Rename robots in Sphero Edu app before expo day.
5. Input lag in manual crowding:
   - Use inferred mode for high robot counts.
   - Assign one operator to crowding terminal only.

## 11) If 8 Robots Is Unreliable on One Laptop (Fallback)

Use 2 laptops, same codebase, same schedule, same logging schema:

- Laptop A controls 3-4 robots with its own `config.json`
- Laptop B controls 3-4 robots with its own `config.json`
- Run the same trial clock start (countdown sync) and same `lambda`
- Keep CSV format identical from both laptops
- Merge/analyze files later by timestamp and `robot_id`

This preserves experiment design while reducing BLE contention per adapter.
