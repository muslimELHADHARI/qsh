from __future__ import annotations

import random
from dataclasses import dataclass

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

_SIMULATOR = AerSimulator()


@dataclass(slots=True)
class ExchangeMaterial:
    bits: list[int]
    bases: list[int]


@dataclass(slots=True)
class BB84Result:
    sifted_bits: list[int]
    qber: float


@dataclass(slots=True)
class EveStats:
    mode: str
    intercept_count: int
    intercept_rate_observed: float


def generate_material(num_bits: int) -> ExchangeMaterial:
    return ExchangeMaterial(
        bits=[random.randint(0, 1) for _ in range(num_bits)],
        bases=[random.randint(0, 1) for _ in range(num_bits)],
    )


def _build_single_qubit_circuit(bit_value: int, prepared_basis: int, measure_basis: int) -> QuantumCircuit:
    qc = QuantumCircuit(1, 1)
    if bit_value == 1:
        qc.x(0)
    if prepared_basis == 1:
        qc.h(0)
    if measure_basis == 1:
        qc.h(0)
    qc.measure(0, 0)
    return qc


def _measure_batch(prepared_bits: list[int], prepared_bases: list[int], measure_bases: list[int]) -> list[int]:
    circuits = [
        _build_single_qubit_circuit(bit, prep_basis, meas_basis)
        for bit, prep_basis, meas_basis in zip(prepared_bits, prepared_bases, measure_bases)
    ]
    if not circuits:
        return []
    job = _SIMULATOR.run(circuits, shots=1, memory=True)
    result = job.result()
    out: list[int] = []
    for idx in range(len(circuits)):
        out.append(int(result.get_memory(idx)[0]))
    return out


def measure_material(sender: ExchangeMaterial, receiver_bases: list[int], noise_rate: float = 0.0) -> list[int]:
    measured = _measure_batch(sender.bits, sender.bases, receiver_bases)
    for i, bit in enumerate(measured):
        if random.random() < noise_rate:
            measured[i] = 1 - bit
    return measured


def measure_with_eve_intercept(
    sender: ExchangeMaterial,
    receiver_bases: list[int],
    eve_intercept_rate: float,
    eve_mode: str = "random",
    eve_basis_bias: float = 0.5,
    noise_rate: float = 0.0,
) -> tuple[list[int], EveStats]:
    n = len(receiver_bases)
    send_bits = list(sender.bits)
    send_bases = list(sender.bases)

    intercept_indexes: list[int] = []
    eve_bases: list[int] = []
    for i in range(n):
        if random.random() < eve_intercept_rate:
            intercept_indexes.append(i)
            if eve_mode == "biased":
                eve_bases.append(1 if random.random() < eve_basis_bias else 0)
            else:
                eve_bases.append(random.randint(0, 1))

    intercept_count = len(intercept_indexes)

    # Eve performs the first batch measurement on intercepted qubits.
    if intercept_count:
        eve_in_bits = [send_bits[i] for i in intercept_indexes]
        eve_in_bases = [send_bases[i] for i in intercept_indexes]
        eve_out_bits = _measure_batch(eve_in_bits, eve_in_bases, eve_bases)
        for idx, eve_bit, eve_basis in zip(intercept_indexes, eve_out_bits, eve_bases):
            send_bits[idx] = eve_bit
            send_bases[idx] = eve_basis

    # Bob measures all qubits in one batch.
    measured = _measure_batch(send_bits, send_bases, receiver_bases)
    for i, bit in enumerate(measured):
        if random.random() < noise_rate:
            measured[i] = 1 - bit
    observed = intercept_count / len(receiver_bases) if receiver_bases else 0.0
    return measured, EveStats(mode=eve_mode, intercept_count=intercept_count, intercept_rate_observed=observed)


def sift_key(
    sender_bits: list[int],
    sender_bases: list[int],
    receiver_bits: list[int],
    receiver_bases: list[int],
    sample_size: int,
    sample_indexes: list[int] | None = None,
) -> BB84Result:
    matching = [i for i, (a, b) in enumerate(zip(sender_bases, receiver_bases)) if a == b]
    if not matching:
        return BB84Result([], 1.0)

    s_bits = [sender_bits[i] for i in matching]
    r_bits = [receiver_bits[i] for i in matching]
    check_count = min(sample_size, len(s_bits) // 2)
    if sample_indexes is None:
        check_idx = set(random.sample(range(len(s_bits)), check_count)) if check_count else set()
    else:
        check_idx = set(sample_indexes[:check_count])

    mismatches = 0
    key: list[int] = []
    for i, (s_bit, r_bit) in enumerate(zip(s_bits, r_bits)):
        if i in check_idx:
            if s_bit != r_bit:
                mismatches += 1
        elif s_bit == r_bit:
            key.append(s_bit)

    qber = mismatches / len(check_idx) if check_idx else 0.0
    return BB84Result(key, qber)


def bits_to_bytes(bits: list[int]) -> bytes:
    if not bits:
        return b""
    padded = bits + [0] * ((8 - len(bits) % 8) % 8)
    out = bytearray()
    for i in range(0, len(padded), 8):
        value = 0
        for bit in padded[i : i + 8]:
            value = (value << 1) | bit
        out.append(value)
    return bytes(out)
