from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from crypto.bb84 import generate_material, measure_with_eve_intercept, sift_key  # noqa: E402


def run_trial(
    bits: int,
    sample_size: int,
    eve_rate: float,
    eve_mode: str,
    eve_bias: float,
    noise_rate: float,
) -> tuple[float, int]:
    alice = generate_material(bits)
    bob_bases = generate_material(bits).bases
    bob_bits, eve_stats = measure_with_eve_intercept(
        alice,
        bob_bases,
        eve_intercept_rate=eve_rate,
        eve_mode=eve_mode,
        eve_basis_bias=eve_bias,
        noise_rate=noise_rate,
    )
    result = sift_key(
        sender_bits=alice.bits,
        sender_bases=alice.bases,
        receiver_bits=bob_bits,
        receiver_bases=bob_bases,
        sample_size=sample_size,
    )
    return result.qber, eve_stats.intercept_count


def run_rate_sweep(
    trials: int,
    bits: int,
    sample_size: int,
    threshold: float,
    noise_rate: float,
    eve_rates: list[float],
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    total_conditions = 2 * len(eve_rates)
    cond_idx = 0
    for mode in ["random", "biased"]:
        for eve_rate in eve_rates:
            cond_idx += 1
            qbers: list[float] = []
            accepts = 0
            intercept_counts: list[int] = []
            for _ in range(trials):
                bias = 0.85 if mode == "biased" else 0.5
                qber, intercept_count = run_trial(
                    bits=bits,
                    sample_size=sample_size,
                    eve_rate=eve_rate,
                    eve_mode=mode,
                    eve_bias=bias,
                    noise_rate=noise_rate,
                )
                qbers.append(qber)
                intercept_counts.append(intercept_count)
                if qber <= threshold:
                    accepts += 1

            rows.append(
                {
                    "mode": mode,
                    "eve_rate": eve_rate,
                    "qber_mean": statistics.mean(qbers),
                    "qber_stdev": statistics.pstdev(qbers),
                    "accept_prob": accepts / trials,
                    "mean_intercepts": statistics.mean(intercept_counts),
                }
            )
            print(
                f"[rate-sweep] {cond_idx}/{total_conditions} "
                f"mode={mode} rate={eve_rate:.2f} done"
            )
    return rows


def run_bias_grid(
    trials: int,
    bits: int,
    sample_size: int,
    threshold: float,
    noise_rate: float,
    eve_rates: list[float],
    biases: list[float],
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    total_conditions = len(eve_rates) * len(biases)
    cond_idx = 0
    for eve_rate in eve_rates:
        for bias in biases:
            cond_idx += 1
            qbers: list[float] = []
            accepts = 0
            for _ in range(trials):
                qber, _ = run_trial(
                    bits=bits,
                    sample_size=sample_size,
                    eve_rate=eve_rate,
                    eve_mode="biased",
                    eve_bias=bias,
                    noise_rate=noise_rate,
                )
                qbers.append(qber)
                if qber <= threshold:
                    accepts += 1
            rows.append(
                {
                    "eve_rate": eve_rate,
                    "eve_bias": bias,
                    "qber_mean": statistics.mean(qbers),
                    "accept_prob": accepts / trials,
                }
            )
            print(
                f"[bias-grid] {cond_idx}/{total_conditions} "
                f"rate={eve_rate:.2f} bias={bias:.2f} done"
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_rate_sweep(rows: list[dict[str, float | str]], out_dir: Path, threshold: float) -> None:
    random_rows = [r for r in rows if r["mode"] == "random"]
    biased_rows = [r for r in rows if r["mode"] == "biased"]

    for subset, title, out_name in [
        (random_rows, "Random-Basis Eve", "qber_vs_eve_rate_random.png"),
        (biased_rows, "Biased-Basis Eve (bias=0.85)", "qber_vs_eve_rate_biased.png"),
    ]:
        x = [float(r["eve_rate"]) for r in subset]
        y = [float(r["qber_mean"]) for r in subset]
        plt.figure(figsize=(7, 4))
        plt.plot(x, y, marker="o")
        plt.axhline(y=threshold, linestyle="--", linewidth=1.3, label=f"QBER threshold={threshold:.2f}")
        plt.xlabel("Eve Intercept Probability")
        plt.ylabel("Mean QBER")
        plt.title(f"QBER vs Eve Rate ({title})")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / out_name, dpi=180)
        plt.close()

    plt.figure(figsize=(7, 4))
    for subset, label in [(random_rows, "random"), (biased_rows, "biased (0.85)")]:
        x = [float(r["eve_rate"]) for r in subset]
        y = [float(r["accept_prob"]) for r in subset]
        plt.plot(x, y, marker="o", label=label)
    plt.xlabel("Eve Intercept Probability")
    plt.ylabel("Handshake Acceptance Probability")
    plt.title("Probability of Undetected Interception")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "acceptance_vs_eve_rate.png", dpi=180)
    plt.close()


def plot_bias_heatmaps(rows: list[dict[str, float]], out_dir: Path) -> None:
    eve_rates = sorted({r["eve_rate"] for r in rows})
    eve_biases = sorted({r["eve_bias"] for r in rows})
    qber_grid = [[0.0 for _ in eve_biases] for _ in eve_rates]
    accept_grid = [[0.0 for _ in eve_biases] for _ in eve_rates]
    idx_rate = {v: i for i, v in enumerate(eve_rates)}
    idx_bias = {v: i for i, v in enumerate(eve_biases)}

    for row in rows:
        i = idx_rate[row["eve_rate"]]
        j = idx_bias[row["eve_bias"]]
        qber_grid[i][j] = row["qber_mean"]
        accept_grid[i][j] = row["accept_prob"]

    for grid, cmap, title, out_name in [
        (qber_grid, "magma", "QBER Heatmap (Biased Eve)", "heatmap_qber_bias_vs_rate.png"),
        (accept_grid, "viridis", "Acceptance Probability Heatmap", "heatmap_acceptance_bias_vs_rate.png"),
    ]:
        plt.figure(figsize=(7, 4.8))
        im = plt.imshow(grid, cmap=cmap, origin="lower", aspect="auto")
        plt.colorbar(im)
        plt.xticks(range(len(eve_biases)), [f"{b:.2f}" for b in eve_biases])
        plt.yticks(range(len(eve_rates)), [f"{r:.2f}" for r in eve_rates])
        plt.xlabel("Eve Basis Bias (P[X basis])")
        plt.ylabel("Eve Intercept Probability")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(out_dir / out_name, dpi=180)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QKD/Eve figures for report")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--bits", type=int, default=128)
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.18)
    parser.add_argument("--noise-rate", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=["quick", "full"], default="quick")
    parser.add_argument("--data-dir", default=str(ROOT / "report" / "data"))
    parser.add_argument("--fig-dir", default=str(ROOT / "report" / "figures"))
    args = parser.parse_args()

    random.seed(args.seed)

    data_dir = Path(args.data_dir)
    fig_dir = Path(args.fig_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    if args.profile == "quick":
        eve_rates_sweep = [0.0, 0.25, 0.5, 0.75, 1.0]
        eve_rates_grid = [0.2, 0.5, 0.8, 1.0]
        biases_grid = [0.0, 0.5, 0.9]
    else:
        eve_rates_sweep = [i / 10 for i in range(0, 11)]
        eve_rates_grid = [0.2, 0.4, 0.6, 0.8, 1.0]
        biases_grid = [0.0, 0.25, 0.5, 0.75, 1.0]

    t0 = time.perf_counter()
    print(
        f"Generating QKD figures profile={args.profile} trials={args.trials} "
        f"bits={args.bits} sample={args.sample_size}"
    )

    rate_rows = run_rate_sweep(
        trials=args.trials,
        bits=args.bits,
        sample_size=args.sample_size,
        threshold=args.threshold,
        noise_rate=args.noise_rate,
        eve_rates=eve_rates_sweep,
    )
    bias_rows = run_bias_grid(
        trials=args.trials,
        bits=args.bits,
        sample_size=args.sample_size,
        threshold=args.threshold,
        noise_rate=args.noise_rate,
        eve_rates=eve_rates_grid,
        biases=biases_grid,
    )

    write_csv(data_dir / "rate_sweep.csv", rate_rows)
    write_csv(data_dir / "bias_grid.csv", bias_rows)
    plot_rate_sweep(rate_rows, fig_dir, threshold=args.threshold)
    plot_bias_heatmaps(bias_rows, fig_dir)

    elapsed = time.perf_counter() - t0
    print(f"Wrote data to: {data_dir}")
    print(f"Wrote figures to: {fig_dir}")
    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
