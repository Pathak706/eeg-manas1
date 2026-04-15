from dataclasses import dataclass, field
import numpy as np
from scipy.signal import butter, sosfiltfilt, iirnotch, sosfilt, resample_poly
from math import gcd

from utils.signal_utils import compute_band_powers, dominant_frequency


@dataclass
class PreprocessedEEG:
    epochs: list[np.ndarray]          # list of (n_channels, epoch_samples)
    display_data: np.ndarray           # (n_channels, n_display_samples) — downsampled
    display_sample_rate: int
    original_sample_rate: int
    channel_names: list[str]
    duration_sec: float
    epoch_duration_sec: float
    epoch_start_times: list[float]
    band_powers_per_epoch: list[dict]  # one dict per epoch
    dominant_freqs_per_epoch: list[float]


class EEGPreprocessor:
    BANDPASS_LOW_HZ = 0.5
    BANDPASS_HIGH_HZ = 40.0
    NOTCH_FREQ_HZ = 50.0
    EPOCH_DURATION_SEC = 4.0
    EPOCH_OVERLAP_SEC = 0.5

    def __init__(self, sample_rate: int, channel_names: list[str]):
        self.sample_rate = sample_rate
        self.channel_names = channel_names

    def bandpass_filter(self, data: np.ndarray) -> np.ndarray:
        """4th-order Butterworth bandpass filter. data: (n_ch, n_samples)."""
        sos = butter(
            4,
            [self.BANDPASS_LOW_HZ, self.BANDPASS_HIGH_HZ],
            btype="bandpass",
            fs=self.sample_rate,
            output="sos",
        )
        return sosfiltfilt(sos, data, axis=1)

    def notch_filter(self, data: np.ndarray, freq: float = None) -> np.ndarray:
        """IIR notch filter to remove power-line noise (50 Hz in India)."""
        freq = freq or self.NOTCH_FREQ_HZ
        b, a = iirnotch(freq, Q=30.0, fs=self.sample_rate)
        # Convert to sos for numerical stability
        from scipy.signal import tf2sos
        sos = tf2sos(b, a)
        return sosfilt(sos, data, axis=1)

    def normalize_channels(self, data: np.ndarray) -> np.ndarray:
        """Per-channel robust z-score using median and IQR."""
        median = np.median(data, axis=1, keepdims=True)
        q75 = np.percentile(data, 75, axis=1, keepdims=True)
        q25 = np.percentile(data, 25, axis=1, keepdims=True)
        iqr = q75 - q25
        iqr = np.where(iqr == 0, 1.0, iqr)
        return (data - median) / iqr

    def segment_epochs(self, data: np.ndarray) -> tuple[list[np.ndarray], list[float]]:
        """
        Segment data into overlapping epochs.
        Returns (epochs, start_times_sec).
        data: (n_channels, n_samples)
        """
        epoch_samples = int(self.EPOCH_DURATION_SEC * self.sample_rate)
        step_samples = int((self.EPOCH_DURATION_SEC - self.EPOCH_OVERLAP_SEC) * self.sample_rate)
        n_samples = data.shape[1]

        epochs = []
        start_times = []
        start = 0
        while start + epoch_samples <= n_samples:
            epochs.append(data[:, start:start + epoch_samples])
            start_times.append(start / self.sample_rate)
            start += step_samples

        return epochs, start_times

    def downsample_for_display(self, data: np.ndarray, target_rate: int = 250) -> np.ndarray:
        """Anti-aliased downsampling using polyphase resampling."""
        if self.sample_rate == target_rate:
            return data
        g = gcd(target_rate, self.sample_rate)
        up = target_rate // g
        down = self.sample_rate // g
        return resample_poly(data, up, down, axis=1)

    def preprocess(self, raw_data: np.ndarray, target_display_rate: int = 250) -> PreprocessedEEG:
        """Full pipeline: bandpass → notch → normalize → epoch → features."""
        n_samples = raw_data.shape[1]
        duration_sec = n_samples / self.sample_rate

        # Filtering
        filtered = self.bandpass_filter(raw_data)
        filtered = self.notch_filter(filtered)

        # Downsample for display (before normalization to keep μV scale for viewer)
        display_data = self.downsample_for_display(filtered, target_display_rate)

        # Normalize for ML
        normalized = self.normalize_channels(filtered)

        # Epoch
        epochs, start_times = self.segment_epochs(normalized)

        # Per-epoch features
        band_powers_list = []
        dominant_freqs = []
        for epoch in epochs:
            band_powers_list.append(compute_band_powers(epoch, self.sample_rate))
            dominant_freqs.append(dominant_frequency(epoch, self.sample_rate))

        return PreprocessedEEG(
            epochs=epochs,
            display_data=display_data,
            display_sample_rate=target_display_rate,
            original_sample_rate=self.sample_rate,
            channel_names=self.channel_names,
            duration_sec=duration_sec,
            epoch_duration_sec=self.EPOCH_DURATION_SEC,
            epoch_start_times=start_times,
            band_powers_per_epoch=band_powers_list,
            dominant_freqs_per_epoch=dominant_freqs,
        )
