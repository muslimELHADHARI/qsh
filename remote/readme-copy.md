# QSH (Quantum-inspired Secure Shell)

QSH is a **research prototype** that simulates BB84-style key exchange, then switches to a classical encrypted transport layer using:

- `qiskit` + `qiskit-aer` for BB84 qubit simulation
- `cryptography` (Python)
- `AES-GCM` for authenticated encryption
- `HKDF` for session key derivation

After handshake, QSH supports:

- remote shell commands
- file upload
- file download

> Warning: This is **not production security**. BB84 is simulated over a normal classical network for experimentation.

## Project Structure

- `app/crypto/bb84.py` - BB84 simulation primitives
- `app/crypto/bb84.py` - BB84 simulation primitives (Qiskit + Aer)
- `app/crypto/kdf.py` - HKDF-based key derivation
- `app/crypto/cipher.py` - AES-GCM framed transport with sequence checks
- `app/core/client.py` - client operations
- `app/server/controller.py` - server runtime/controller
- `app/agent/executor.py` - shell action handler
- `app/agent/file_transfer.py` - file transfer handler
- `docs/protocol.md` - protocol details and message flow
- `app/tests/` - basic tests

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

### 1) Start server

```bash
.venv\Scripts\python app/server.py --host 127.0.0.1 --port 8022
```

### 2) Execute remote shell command

```bash
.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 shell "whoami"
```

### 3) Upload file

```bash
.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 upload ".\README.md" ".\remote\readme-copy.md"
```

### 4) Download file

```bash
.venv\Scripts\python app/main.py --host 127.0.0.1 --port 8022 download ".\remote\readme-copy.md" ".\downloaded\readme-copy.md"
```

## Simulating Noise / Eavesdropping Effects

Use `--noise-rate` in the client to inject measurement noise in BB84 simulation:

```bash
.venv\Scripts\python app/main.py --noise-rate 0.10 --host 127.0.0.1 --port 8022 shell "echo test"
```

Higher noise raises QBER (quantum bit error rate). If QBER is above threshold, handshake fails.

## Test

```bash
set PYTHONPATH=app
.venv\Scripts\python -m pytest app/tests -q
```

## Security and Research Notes

- BB84 is simulated, not implemented on physical quantum channels.
- This prototype helps study QBER behavior and key survival rates under noise.
- `AES-GCM` nonces are random per frame and protected with sequence-bound AAD.
- Replay/ordering attacks are mitigated with strict receive sequence validation.
