from app.crypto.bb84 import generate_material, measure_with_eve_intercept, sift_key
import random

alice = generate_material(512)
bob_bases = generate_material(512).bases
sample_idx = random.sample(range(512), 32)
measured, eve_stats = measure_with_eve_intercept(alice, bob_bases, 0.8, "biased", 0.9)
res = sift_key(alice.bits, alice.bases, measured, bob_bases, 32, sample_idx)
print(f"Eve stats: {eve_stats}")
print(f"QBER: {res.qber}")
