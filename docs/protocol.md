# QSH Protocol Notes

## 1. Goals

QSH is a research protocol inspired by SSH with:

- simulated BB84 key exchange using `qiskit` + `qiskit-aer`
- classical authenticated encryption for transport
- remote shell execution and file transfer actions

## 2. Handshake Flow

1. `HELLO` (client -> server)
2. `BB84_CLIENT_DATA` (client -> server)
   - sender bits
   - sender bases
   - receiver bases
   - measured bits
   - HKDF salt
3. Server performs sifting and QBER estimation.
4. Server returns `BB84_RESULT` with:
   - `accepted` flag
   - `qber`
   - `session_id_hex` on success
5. Both sides derive AES key from sifted bits using HKDF.
6. Session switches to encrypted framed traffic.

## 3. Key Derivation

- Input material: sifted BB84 bits serialized to bytes.
- KDF: HKDF-SHA256 with context label `qsh-session-derivation`.
- Output:
  - AES key (default 32 bytes)
  - session id (16 bytes)

## 4. Encrypted Framing

Each secure frame contains:

- `sequence` (uint64)
- `nonce` (12 random bytes)
- `ciphertext_length` (uint32)
- `ciphertext || tag` from AES-GCM

Additional Authenticated Data (AAD) is the `sequence`.

Receiver enforces exact sequence order to mitigate replay/out-of-order frames.

## 5. Application Actions

Encrypted request payload field: `action`

- `shell`: execute command on server
- `upload`: send base64 file content to server path
- `download`: receive base64 file content from server path
- `quit`: close session

## 6. Research Limitations

- BB84 is simulated with software circuits (`AerSimulator`), not via quantum hardware.
- No forward secrecy guarantees beyond simulated model assumptions.
- No user authentication model (keys/passwords/certificates) yet.
- Single-command shell mode, not full PTY interactive terminal.

## 7. Possible Extensions

- Add authenticated identity layer (certificates/signatures).
- Add chunked file transfer and resume support.
- Add compression negotiation.
- Add multi-channel multiplexing with channel ids.
- Add richer simulation model (intercept-resend attacker behavior, detector inefficiency).
