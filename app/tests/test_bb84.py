from crypto.bb84 import bits_to_bytes, generate_material, measure_material, measure_with_eve_intercept, sift_key


def test_bb84_sift_produces_key():
    material = generate_material(128)
    receiver_bases = generate_material(128).bases
    receiver_bits = measure_material(material, receiver_bases, noise_rate=0.0)
    result = sift_key(material.bits, material.bases, receiver_bits, receiver_bases, sample_size=16)
    assert 0.0 <= result.qber <= 1.0
    assert isinstance(bits_to_bytes(result.sifted_bits), bytes)


def test_eve_intercept_increases_qber():
    material = generate_material(512)
    receiver_bases = generate_material(512).bases
    receiver_bits, stats = measure_with_eve_intercept(material, receiver_bases, eve_intercept_rate=1.0, noise_rate=0.0)
    result = sift_key(material.bits, material.bases, receiver_bits, receiver_bases, sample_size=64)
    assert stats.intercept_count > 0
    assert result.qber > 0.05


def test_eve_biased_mode_stats():
    material = generate_material(128)
    receiver_bases = generate_material(128).bases
    _, stats = measure_with_eve_intercept(
        material,
        receiver_bases,
        eve_intercept_rate=0.5,
        eve_mode="biased",
        eve_basis_bias=0.9,
        noise_rate=0.0,
    )
    assert stats.mode == "biased"
    assert 0.2 <= stats.intercept_rate_observed <= 0.8
