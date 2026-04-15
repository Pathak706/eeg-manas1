import numpy as np
from scipy.signal import welch


BAND_RANGES = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}


def compute_band_powers(epoch: np.ndarray, sample_rate: int) -> dict[str, float]:
    """
    Compute average band power across all channels for one epoch.
    epoch shape: (n_channels, n_samples)
    Returns dict with band names as keys and mean power as values.
    """
    # Average signal across channels for a representative PSD
    mean_signal = np.mean(epoch, axis=0)
    freqs, psd = welch(mean_signal, fs=sample_rate, nperseg=min(256, len(mean_signal)))

    powers = {}
    total = 0.0
    try:
        _trapz = np.trapezoid  # NumPy >= 2.0
    except AttributeError:
        _trapz = np.trapz      # NumPy < 2.0
    for band, (low, high) in BAND_RANGES.items():
        idx = np.where((freqs >= low) & (freqs <= high))[0]
        power = float(_trapz(psd[idx], freqs[idx])) if len(idx) > 0 else 0.0
        powers[band] = power
        total += power

    # Normalize to relative band power
    if total > 0:
        powers = {k: v / total for k, v in powers.items()}

    return powers


def dominant_frequency(epoch: np.ndarray, sample_rate: int) -> float:
    """Return the frequency with peak power across 0.5–40 Hz."""
    mean_signal = np.mean(epoch, axis=0)
    freqs, psd = welch(mean_signal, fs=sample_rate, nperseg=min(256, len(mean_signal)))
    idx = np.where((freqs >= 0.5) & (freqs <= 40.0))[0]
    if len(idx) == 0:
        return 0.0
    peak_idx = idx[np.argmax(psd[idx])]
    return float(freqs[peak_idx])


def channel_rms(data: np.ndarray) -> np.ndarray:
    """RMS amplitude per channel. data shape: (n_channels, n_samples)."""
    return np.sqrt(np.mean(data ** 2, axis=1))


# ── Depression biomarker utilities ─────────────────────────────────────────

# Frontal channel pairs for asymmetry computation (left, right)
FRONTAL_PAIRS = [("F3", "F4"), ("Fp1", "Fp2"), ("F7", "F8")]


def compute_band_powers_per_channel(
    epoch: np.ndarray, sample_rate: int, channel_names: list[str]
) -> dict[str, dict[str, float]]:
    """
    Compute relative band power for each channel individually.
    epoch shape: (n_channels, n_samples)
    Returns {channel_name: {band_name: relative_power}}.
    """
    try:
        _trapz = np.trapezoid
    except AttributeError:
        _trapz = np.trapz

    result = {}
    for i, ch in enumerate(channel_names):
        signal = epoch[i]
        freqs, psd = welch(signal, fs=sample_rate, nperseg=min(256, len(signal)))

        powers = {}
        total = 0.0
        for band, (low, high) in BAND_RANGES.items():
            idx = np.where((freqs >= low) & (freqs <= high))[0]
            power = float(_trapz(psd[idx], freqs[idx])) if len(idx) > 0 else 0.0
            powers[band] = power
            total += power

        if total > 0:
            powers = {k: v / total for k, v in powers.items()}

        result[ch] = powers

    return result


def compute_frontal_alpha_asymmetry(
    per_channel_powers: dict[str, dict[str, float]],
    channel_names: list[str],
) -> float:
    """
    Compute Frontal Alpha Asymmetry (FAA).
    FAA = ln(alpha_right) - ln(alpha_left)
    Negative FAA is associated with depression (reduced left frontal alpha).
    Uses the first available frontal pair from FRONTAL_PAIRS.
    """
    for left_ch, right_ch in FRONTAL_PAIRS:
        if left_ch in per_channel_powers and right_ch in per_channel_powers:
            alpha_left = per_channel_powers[left_ch].get("alpha", 0.0)
            alpha_right = per_channel_powers[right_ch].get("alpha", 0.0)
            # Add epsilon to avoid log(0)
            eps = 1e-10
            return float(np.log(alpha_right + eps) - np.log(alpha_left + eps))

    return 0.0  # no frontal pair found
