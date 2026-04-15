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
    seizure_onset_sec: float | None
    seizure_duration_sec: float | None


class SyntheticEEGGenerator:
    SAMPLE_RATE = 256
    DURATION_SEC = 120

    def generate(
        self,
        include_seizure: bool = True,
        seizure_onset_sec: float = 45.0,
        seizure_duration_sec: float = 20.0,
        seed: int = 42,
    ) -> SyntheticEEGResult:
        rng = np.random.default_rng(seed)
        n_samples = int(self.SAMPLE_RATE * self.DURATION_SEC)
        t = np.arange(n_samples) / self.SAMPLE_RATE

        data = self._generate_background(t, rng)

        if include_seizure:
            data = self._inject_seizure(data, t, seizure_onset_sec, seizure_duration_sec, rng)

        data = self._inject_artifacts(data, t, rng)

        return SyntheticEEGResult(
            data=data,
            channel_names=CHANNELS_10_20,
            sample_rate=self.SAMPLE_RATE,
            duration_sec=self.DURATION_SEC,
            seizure_onset_sec=seizure_onset_sec if include_seizure else None,
            seizure_duration_sec=seizure_duration_sec if include_seizure else None,
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

    def _inject_seizure(
        self,
        data: np.ndarray,
        t: np.ndarray,
        onset_sec: float,
        duration_sec: float,
        rng: np.random.Generator,
    ) -> np.ndarray:
        sr = self.SAMPLE_RATE
        onset_idx = int(onset_sec * sr)
        end_idx = min(int((onset_sec + duration_sec) * sr), data.shape[1])

        # Spatial weights: focal on T3/T4 left temporal
        focus = np.array(CHANNEL_COORDS["T3"])
        weights = np.zeros(len(CHANNELS_10_20))
        for i, ch in enumerate(CHANNELS_10_20):
            coord = np.array(CHANNEL_COORDS.get(ch, (0, 0, 0)))
            dist = np.linalg.norm(coord - focus)
            weights[i] = np.exp(-(dist ** 2) / (2 * 0.4 ** 2))

        phase1_end = min(onset_idx + int(4 * sr), end_idx)
        phase2_end = min(phase1_end + int((duration_sec - 7) * sr), end_idx)
        phase3_end = end_idx

        # Phase 1: fast ripples 70 Hz
        t_p1 = t[onset_idx:phase1_end] - onset_sec
        for i, ch in enumerate(CHANNELS_10_20):
            amp = weights[i] * 50
            fast = amp * np.sin(2 * np.pi * 70 * t_p1 + rng.uniform(0, 2 * np.pi))
            data[i, onset_idx:phase1_end] += fast

        # Phase 2: rhythmic spike-wave 3.5 Hz building amplitude
        t_p2 = t[phase1_end:phase2_end] - (onset_sec + 4)
        ramp = np.linspace(1.0, 3.0, phase2_end - phase1_end)
        for i, ch in enumerate(CHANNELS_10_20):
            amp = weights[i] * 80
            spike_wave = amp * ramp * np.sin(2 * np.pi * 3.5 * t_p2 + rng.uniform(0, 2 * np.pi))
            data[i, phase1_end:phase2_end] += spike_wave

        # Phase 3: post-ictal attenuation
        data[:, phase2_end:phase3_end] *= 0.2

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
