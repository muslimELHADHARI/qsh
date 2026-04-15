# QSH Usage Guide

This guide explains how to run and use QSH end-to-end.

---

## 1) What QSH Does

QSH is a research prototype that provides:

- Simulated BB84/QKD key exchange (`qiskit` + `qiskit-aer`)
- Session key derivation using HKDF
- Encrypted transport with AES-GCM
- Password authentication over the encrypted channel
- Remote shell command execution
- File upload and download
- Persistent interactive session mode (SSH-like behavior)

> Important: This is a research/educational system, not production security software.

---

## 2) Requirements

- Windows PowerShell (commands below are PowerShell style)
- Python installed
- Project root:
  - `C:\Users\DELL\Documents\GitHub\qsh`

---

## 3) Initial Setup

Open PowerShell:

```powershell
cd "C:\Users\DELL\Documents\GitHub\qsh"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

---

## 4) Run Tests

```powershell
cd "C:\Users\DELL\Documents\GitHub\qsh"
$env:PYTHONPATH="app"
.\.venv\Scripts\python -m pytest app/tests -q
```

Expected output includes:

- `6 passed`

---

## 5) Start the Server

Choose host/port and server password:

```powershell
cd "C:\Users\DELL\Documents\GitHub\qsh"
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --server-password "abc123" server
```

You should see logs similar to:

- listening message
- session connection logs
- QKD handshake logs
- authentication success/failure logs

---

## 6) Client One-Shot Commands

All client commands must use the same host/port and matching password.

### Remote Shell Command

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" shell "whoami"
```

### Upload File

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" upload ".\README.md" ".\remote\readme-copy.md"
```

### Download File

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" download ".\remote\readme-copy.md" ".\downloaded\readme-copy.md"
```

### Verify File Integrity (Optional)

```powershell
Get-FileHash ".\README.md" -Algorithm SHA256
Get-FileHash ".\downloaded\readme-copy.md" -Algorithm SHA256
```

If hashes match, transfer is correct.

---

## 7) Persistent Session Mode (Recommended)

This mode keeps one connection alive and lets you execute many operations without reconnecting each time.

Start session:

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" session
```

Inside prompt:

```text
qsh> shell whoami
qsh> shell dir
qsh> upload .\README.md .\remote\readme-copy.md
qsh> download .\remote\readme-copy.md .\downloaded\readme-copy.md
qsh> help
qsh> exit
```

Supported prompt commands:

- `shell <command>`
- `upload <local_path> <remote_path>`
- `download <remote_path> <local_path>`
- `help`
- `exit` / `quit`

---

## 8) QKD and Session Logs

During connection, QSH prints status such as:

- Client sending `HELLO`
- BB84 exchange size (number of qubits)
- QBER value and sifted key length
- Derived session ID
- Server session labels (`S0001`, `S0002`, ...)
- Action logs (`shell`, `upload`, `download`, `auth`)

These logs help you observe protocol behavior during research.

---

## 8b) Eve Scenario (Intercept-Resend)

QSH supports Eve simulation modes on the client side of the BB84 experiment.

Use `--eve-rate` with value from `0.0` to `1.0`:

- `0.0` = no Eve
- `1.0` = Eve intercepts every qubit

Use `--eve-mode`:

- `random`: Eve picks basis randomly (Z or X)
- `biased`: Eve picks X basis with probability `--eve-bias` (default `0.5`)

Example (one-shot):

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" --eve-rate 1.0 shell "whoami"
```

Example (biased Eve):

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" --eve-rate 0.8 --eve-mode biased --eve-bias 0.9 shell "whoami"
```

Example (persistent session):

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" --eve-rate 1.0 session
```

When Eve is active, QBER tends to rise. If QBER crosses threshold, handshake is rejected.

QKD report lines now include:

- `sifted_rate`
- `qber`
- `eve_mode`
- `eve_intercepts`
- `eve_observed_rate`

---

## 9) Authentication Behavior

Authentication happens after encrypted session establishment:

1. QKD + HKDF + AES-GCM session established
2. Client sends password inside encrypted channel
3. Server checks against stored server password
4. Access granted only on success

If password is wrong:

- Client receives auth failure
- Session is denied/closed by server

If you omit `--password` on client, QSH prompts securely using `getpass`.

---

## 9b) Password Hardening Controls

QSH server now supports:

- PBKDF2-SHA256 password hashing
- adaptive throttling on failed auth attempts
- lockout policy after repeated failures

Generate an encoded password hash:

```powershell
.\.venv\Scripts\python app/main.py hash-password --value "abc123"
```

Start server with hash (recommended):

```powershell
.\.venv\Scripts\python app/main.py --server-password-hash 'pbkdf2_sha256$...' --auth-max-failures 5 --auth-lockout-seconds 180 --auth-throttle-base 0.75 server
```

Important:

- Do not use `"pbkdf2_sha256$..."` literally; that is a placeholder.
- Use the full real output from `hash-password`.
- In PowerShell, prefer single quotes for hashes because `$` inside double quotes can be expanded.

Or with plain password (server hashes it in-memory at startup):

```powershell
.\.venv\Scripts\python app/main.py --server-password "abc123" server
```

---

## 9c) Audit Logging and Observability

QSH writes structured logs for:

- startup configuration
- QKD/Eve reports
- session open/close/error
- authentication success/failure/lockout
- commands executed
- file upload/download operations

Default log file:

- `logs/qsh.log`

Change with:

```powershell
.\.venv\Scripts\python app/main.py --log-file ".\logs\qsh-research.log" --server-password "abc123" server
```

---

## 10) LAN / Remote Machine Usage

### Server machine

```powershell
.\.venv\Scripts\python app/main.py --host 0.0.0.0 --port 8022 --server-password "abc123" server
```

### Client machine

Use server LAN IP:

```powershell
.\.venv\Scripts\python app/main.py --host <SERVER_IP> --port 8022 --password "abc123" shell "hostname"
```

Also ensure firewall allows TCP port `8022`.

---

## 11) Troubleshooting

### `ConnectionError: peer disconnected`

- Confirm server is running first.
- Confirm host/port match exactly.
- Check server terminal for session error logs.

### Authentication failure

- Ensure `--password` matches server `--server-password`.
- Avoid trailing spaces/quotes mistakes in shell command.

### Port already in use

- Change to another port on server and client:
  - e.g. `--port 8033`

### Import/test issues

- Run from project root.
- Use `.venv` Python.
- For tests set:
  - `$env:PYTHONPATH="app"`

---

## 12) Quick Command Summary

Server:

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --server-password "abc123" server
```

Client one-shot:

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" shell "whoami"
```

Client persistent:

```powershell
.\.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 --password "abc123" session
```

---

## 13) Generate Research Figures for Report

Quick profile (fast, good for iterative writing):

```powershell
.\.venv\Scripts\python scripts\generate_qkd_figures.py --profile quick
```

Higher-fidelity profile (slower, for final paper plots):

```powershell
.\.venv\Scripts\python scripts\generate_qkd_figures.py --profile full --trials 60 --bits 192 --sample-size 16
```

Outputs:

- CSV data: `report/data/`
- PNG figures: `report/figures/`

Build full report pipeline (figures + LaTeX PDF if available):

```powershell
.\report\build_report.ps1 -Profile quick
```

For heavier experiments:

```powershell
.\report\build_report.ps1 -Profile full -Trials 60 -Bits 192 -SampleSize 16
```

