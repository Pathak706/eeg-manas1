import numpy as np
from dataclasses import dataclass


CHANNELS_10_20 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
]

# Approximate 3D coordinates (x, y, z) for 10-20 channels on unit sphere
# Used for spatial Gaussian propagation of seizure activity
CHANNEL_COORDS = {
    "Fp1": (-0.3, 0.9, 0.3), "Fp2": (0.3, 0.9, 0.3),
    "F7":  (-0.7, 0.5, 0.5), "F8":  (0.7, 0.5, 0.5),
    "F3":  (-0.5, 0.7, 0.5), "F4":  (0.5, 0.7, 0.5),
    "Fz":  (0.0, 0.8, 0.6),
    "T3":  (-1.0, 0.0, 0.0), "T4":  (1.0, 0.0, 0.0),
    "C3":  (-0.5, 0.0, 0.9), "C4":  (0.5, 0.0, 0.9),
    "Cz":  (0.0, 0.0, 1.0),
    "T5":  (-0.7, -0.5, 0.5), "T6": (0.7, -0.5, 0.5),
    "P3":  (-0.5, -0.7, 0.5), "P4": (0.5, -0.7, 0.5),
    "Pz":  (0.0, -0.8, 0.6),
    "O1":  (-0.3, -0.9, 0.3), "O2": (0.3, -0.9, 0.3),
}

# Per-channel amplitude scaling in μV (peak-to-peak / 2)
CHANNEL_AMPLITUDE = {
    "Fp1": 65, "Fp2": 65,
    "F7": 40, "F8": 40,
    "F3": 45, "F4": 45, "Fz": 45,
    "T3": 30, "T4": 30,
    "C3": 35, "C4": 35, "Cz": 35,
    "T5": 30, "T6": 30,
    "P3": 40, "P4": 40, "Pz": 40,
    "O1": 45, "O2": 45,
}

# Alpha weight — occipital channels have strongest alpha
ALPHA_WEIGHT = {
    "O1": 1.0, "O2": 1.0, "P3": 0.6, "P4": 0.6, "Pz": 0.7,
    "T5": 0.4, "T6": 0.4,
}


@dataclass
class SyntheticEEGResult:
    data: np.ndarray          # (n_channels, n_samples) in μV
    channel_names: list[str]
    sample_rate: int
    duration_sec: float
    has_depression_pattern: bool


class SyntheticEEGGenerator:
    SAMPLE_RATE = 256
    DURATION_SEC = 120

    def generate(
        self,
        include_depression: bool = True,
        seed: int = 42,
    ) -> SyntheticEEGResult:
        rng = np.random.default_rng(seed)
        n_samples = int(self.SAMPLE_RATE * self.DURATION_SEC)
        t = np.arange(n_samples) / self.SAMPLE_RATE

        data = self._generate_background(t, rng)

        if include_depression:
            data = self._inject_depression_pattern(data, t, rng)

        data = self._inject_artifacts(data, t, rng)

        return SyntheticEEGResult(
            data=data,
            channel_names=CHANNELS_10_20,
            sample_rate=self.SAMPLE_RATE,
            duration_sec=self.DURATION_SEC,
            has_depression_pattern=include_depression,
        )

    def _generate_background(self, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n_samples = len(t)
        data = np.zeros((len(CHANNELS_10_20), n_samples))

        for i, ch in enumerate(CHANNELS_10_20):
            amp = CHANNEL_AMPLITUDE.get(ch, 35)

            # 1/f (pink-ish) noise via FFT shaping
            white = rng.standard_normal(n_samples)
            fft = np.fft.rfft(white)
            freqs = np.fft.rfftfreq(n_samples, d=1.0 / self.SAMPLE_RATE)
            freqs[0] = 1.0  # avoid divide by zero
            fft /= np.sqrt(freqs) ** 0.8
            pink = np.fft.irfft(fft, n=n_samples)
            pink = pink / (np.std(pink) + 1e-8) * amp * 0.5

            # Alpha rhythm
            alpha_freq = 9.5 + rng.uniform(-0.5, 0.5)
            alpha_phase = rng.uniform(0, 2 * np.pi)
            alpha_amp = ALPHA_WEIGHT.get(ch, 0.1) * amp * 0.6
            alpha = alpha_amp * np.sin(2 * np.pi * alpha_freq * t + alpha_phase)

            # Slow drift (respiration / movement)
            drift_amp = amp * 0.15
            drift_freq = rng.uniform(0.1, 0.3)
            drift = drift_amp * np.sin(2 * np.pi * drift_freq * t + rng.uniform(0, 2 * np.pi))

            data[i] = pink + alpha + drift

        return data

    def _inject_depression_pattern(
        self,
        data: np.ndarray,
        t: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Inject depression-associated EEG patterns across the entire recording:
        1. Left frontal alpha suppression (FAA indicator)
        2. Elevated frontal theta
        3. Overall mild alpha reduction
        These are sustained, subtle changes — not sudden events.
        """
        sr = self.SAMPLE_RATE
        n_samples = data.shape[1]

        # Left frontal channels: suppress alpha by 40-60%
        left_frontal = {"Fp1": 0, "F3": 2, "F7": 10}
        for ch, idx in left_frontal.items():
            if idx < data.shape[0]:
                # Remove a portion of alpha from left frontal
                alpha_freq = 9.5 + rng.uniform(-0.5, 0.5)
                alpha_amp = CHANNEL_AMPLITUDE.get(ch, 35) * ALPHA_WEIGHT.get(ch, 0.1) * 0.6
                suppression = rng.uniform(0.4, 0.6)
                alpha_removal = -alpha_amp * suppression * np.sin(
                    2 * np.pi * alpha_freq * t + rng.uniform(0, 2 * np.pi)
                )
                data[idx] += alpha_removal

        # Elevated frontal theta (5-7 Hz) across frontal channels
        frontal_indices = {
            "Fp1": 0, "Fp2": 1, "F3": 2, "F4": 3,
            "F7": 10, "F8": 11, "Fz": 16,
        }
        for ch, idx in frontal_indices.items():
            if idx < data.shape[0]:
                theta_freq = rng.uniform(5.0, 7.0)
                theta_amp = CHANNEL_AMPLITUDE.get(ch, 35) * rng.uniform(0.2, 0.4)
                theta_signal = theta_amp * np.sin(
                    2 * np.pi * theta_freq * t + rng.uniform(0, 2 * np.pi)
                )
                # Modulate with slow envelope for realism
                envelope = 0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t + rng.uniform(0, 2 * np.pi))
                data[idx] += theta_signal * envelope

        # Mild global alpha suppression (10-20% across all channels)
        global_suppression = rng.uniform(0.10, 0.20)
        for i, ch in enumerate(CHANNELS_10_20):
            alpha_w = ALPHA_WEIGHT.get(ch, 0.1)
            if alpha_w > 0.2:  # only affect channels that have significant alpha
                alpha_freq = 9.5 + rng.uniform(-0.3, 0.3)
                alpha_amp = CHANNEL_AMPLITUDE.get(ch, 35) * alpha_w * 0.6
                reduction = -alpha_amp * global_suppression * np.sin(
                    2 * np.pi * alpha_freq * t + rng.uniform(0, 2 * np.pi)
                )
                data[i] += reduction

        return data

    def _inject_artifacts(
        self,
        data: np.ndarray,
        t: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        sr = self.SAMPLE_RATE
        n_samples = data.shape[1]

        fp1_idx = CHANNELS_10_20.index("Fp1")
        fp2_idx = CHANNELS_10_20.index("Fp2")

        # Eye blinks every 3–8 seconds
        blink_times = np.arange(3, self.DURATION_SEC - 2, rng.uniform(3, 8))
        for bt in blink_times:
            start = int(bt * sr)
            dur = int(0.25 * sr)
            end = min(start + dur, n_samples)
            blink_amp = rng.uniform(150, 300)
            blink_t = np.linspace(0, np.pi, end - start)
            blink_shape = blink_amp * np.sin(blink_t)
            data[fp1_idx, start:end] += blink_shape
            data[fp2_idx, start:end] += blink_shape * 0.9

        # Brief muscle artifact bursts in frontal channels
        f_channels = [CHANNELS_10_20.index(c) for c in ["F7", "F8", "Fp1", "Fp2"] if c in CHANNELS_10_20]
        for _ in range(rng.integers(2, 5)):
            start = rng.integers(5 * sr, (self.DURATION_SEC - 5) * sr)
            dur = rng.integers(int(0.1 * sr), int(0.5 * sr))
            end = min(start + dur, n_samples)
            muscle = rng.standard_normal((len(f_channels), end - start)) * 30
            for j, ch_idx in enumerate(f_channels):
                data[ch_idx, start:end] += muscle[j]

        return data

    def to_numpy(self, result: SyntheticEEGResult) -> dict:
        return {
            "data": result.data,
            "channels": result.channel_names,
            "sample_rate": result.sample_rate,
            "duration_sec": result.duration_sec,
        }
