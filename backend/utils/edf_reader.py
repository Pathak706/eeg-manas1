from dataclasses import dataclass
import numpy as np


@dataclass
class RawEEGData:
    data: np.ndarray          # shape: (n_channels, n_samples)
    channel_names: list[str]
    sample_rate: int
    duration_sec: float
    patient_info: dict


class EDFReader:
    def read(self, file_path: str) -> RawEEGData:
        import pyedflib

        with pyedflib.EdfReader(file_path) as f:
            n_channels = f.signals_in_file
            channel_names = f.getSignalLabels()
            sample_rate = int(f.getSampleFrequency(0))
            n_samples = f.getNSamples()[0]
            duration_sec = n_samples / sample_rate

            data = np.zeros((n_channels, n_samples))
            for i in range(n_channels):
                data[i] = f.readSignal(i)

            header = f.getHeader()
            patient_info = {
                "patient_name": header.get("patientname", ""),
                "recording_date": str(header.get("startdate", "")),
            }

        return RawEEGData(
            data=data,
            channel_names=list(channel_names),
            sample_rate=sample_rate,
            duration_sec=duration_sec,
            patient_info=patient_info,
        )

    def validate_edf(self, file_path: str) -> tuple[bool, str]:
        try:
            import pyedflib
            with pyedflib.EdfReader(file_path) as f:
                n_channels = f.signals_in_file
                if n_channels < 2:
                    return False, f"Too few channels: {n_channels} (minimum 2)"
                sr = int(f.getSampleFrequency(0))
                if sr < 128:
                    return False, f"Sample rate too low: {sr} Hz (minimum 128)"
                n_samples = f.getNSamples()[0]
                duration = n_samples / sr
                if duration < 10:
                    return False, f"Recording too short: {duration:.1f}s (minimum 10s)"
            return True, "OK"
        except Exception as e:
            return False, str(e)
