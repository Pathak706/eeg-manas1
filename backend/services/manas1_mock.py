"""
MANAS-1 Mock Inference Service — Depression Assessment.

Simulates the output contract of the real MANAS-1 400M-parameter EEG foundation model
for depression severity assessment. Uses EEG biomarkers (frontal alpha asymmetry,
alpha/beta ratio, theta elevation) to compute a PHQ-9-equivalent depression score.

To swap in the real model: replace MANAS1MockService with MANAS1HTTPClient that POSTs
preprocessed epoch arrays to the actual inference endpoint and parses the same response types.
"""
import asyncio
import time
from dataclasses import dataclass, field

import numpy as np

from services.eeg_preprocessor import PreprocessedEEG
from config import settings
from utils.signal_utils import (
    compute_band_powers_per_channel,
    compute_frontal_alpha_asymmetry,
    FRONTAL_PAIRS,
)

# Frontal channels for depression biomarker analysis
FRONTAL_CHANNELS = {"Fp1", "Fp2", "F3", "F4", "F7", "F8"}

# PHQ-9 severity mapping
DEPRESSION_LEVELS = [
    (4, "Minimal"),
    (9, "Mild"),
    (14, "Moderate"),
    (19, "Moderately Severe"),
    (27, "Severe"),
]


def phq9_risk_level(score: float) -> str:
    for threshold, label in DEPRESSION_LEVELS:
        if score <= threshold:
            return label
    return "Severe"


@dataclass
class EpochAnalysis:
    epoch_index: int
    start_time_sec: float
    end_time_sec: float
    depression_contribution: float       # 0–1 contribution to session score
    artifact_probability: float
    channel_attention: dict[str, float]
    dominant_frequency_hz: float
    band_powers: dict[str, float]        # averaged across channels
    per_channel_powers: dict[str, dict[str, float]]  # per-channel band powers
    frontal_alpha_asymmetry: float       # per-epoch FAA
    confidence: float


@dataclass
class ClinicalFlag:
    flag_type: str          # DEPRESSIVE_PATTERN | FRONTAL_ASYMMETRY | ALPHA_SUPPRESSION | SLEEP_DISRUPTION
    severity: str           # HIGH | MEDIUM | LOW
    onset_sec: float
    duration_sec: float
    channels_involved: list[str]
    description: str


@dataclass
class BiomarkerSummary:
    alpha_power: float
    beta_power: float
    theta_power: float
    delta_power: float
    gamma_power: float
    frontal_alpha_asymmetry: float
    alpha_beta_ratio: float
    theta_beta_ratio: float


@dataclass
class MANAS1Response:
    model_version: str
    study_id: int
    epochs: list[EpochAnalysis]
    depression_severity_score: float      # 0–27 PHQ-9 equivalent
    depression_risk_level: str            # Minimal/Mild/Moderate/Moderately Severe/Severe
    frontal_alpha_asymmetry: float        # session-level FAA
    biomarkers: BiomarkerSummary
    clinical_flags: list[ClinicalFlag]
    background_rhythm: str
    clinical_impression: str
    processing_time_ms: int


class MANAS1MockService:
    MODEL_VERSION = "manas1-depression-v0.1"

    def __init__(self):
        self.latency_ms = settings.MANAS1_MOCK_LATENCY_MS

    async def analyze_study(
        self,
        preprocessed: PreprocessedEEG,
        study_id: int,
        progress_callback=None,
    ) -> MANAS1Response:
        t_start = time.time()
        n_epochs = len(preprocessed.epochs)
        rng = np.random.default_rng(study_id % 9999)

        # Decide depression severity for this recording
        has_depression = preprocessed.duration_sec > 30
        # Depression is sustained — affects the entire recording, not a window
        base_severity = rng.uniform(0.4, 0.85) if has_depression else rng.uniform(0.05, 0.25)

        epoch_results: list[EpochAnalysis] = []

        for i, epoch in enumerate(preprocessed.epochs):
            result = self._analyze_epoch(
                epoch_data=epoch,
                epoch_index=i,
                start_time_sec=preprocessed.epoch_start_times[i],
                epoch_duration_sec=preprocessed.epoch_duration_sec,
                band_powers=preprocessed.band_powers_per_epoch[i],
                dominant_freq=preprocessed.dominant_freqs_per_epoch[i],
                channel_names=preprocessed.channel_names,
                base_severity=base_severity,
                rng=rng,
                sample_rate=preprocessed.original_sample_rate,
            )
            epoch_results.append(result)

            if progress_callback:
                await progress_callback(i + 1, n_epochs)

            await asyncio.sleep(self.latency_ms / 1000.0)

        # ── Session-level aggregation ──────────────────────────────────────
        contributions = [e.depression_contribution for e in epoch_results]
        avg_contribution = float(np.mean(contributions))

        # Map 0–1 contribution to 0–27 PHQ-9 scale
        depression_score = round(avg_contribution * 27, 1)
        risk_level = phq9_risk_level(depression_score)

        # Session-level FAA (average across epochs)
        session_faa = float(np.mean([e.frontal_alpha_asymmetry for e in epoch_results]))

        # Session biomarkers (average band powers)
        avg_band_powers = self._average_band_powers(preprocessed.band_powers_per_epoch)
        biomarkers = BiomarkerSummary(
            alpha_power=avg_band_powers.get("alpha", 0),
            beta_power=avg_band_powers.get("beta", 0),
            theta_power=avg_band_powers.get("theta", 0),
            delta_power=avg_band_powers.get("delta", 0),
            gamma_power=avg_band_powers.get("gamma", 0),
            frontal_alpha_asymmetry=session_faa,
            alpha_beta_ratio=avg_band_powers.get("alpha", 0) / max(avg_band_powers.get("beta", 0.01), 0.01),
            theta_beta_ratio=avg_band_powers.get("theta", 0) / max(avg_band_powers.get("beta", 0.01), 0.01),
        )

        background_rhythm = self._infer_background_rhythm(avg_band_powers)
        clinical_flags = self._generate_clinical_flags(epoch_results, biomarkers, session_faa)
        clinical_impression = self._generate_clinical_impression(
            clinical_flags, depression_score, risk_level, background_rhythm, biomarkers
        )

        processing_time_ms = int((time.time() - t_start) * 1000)

        return MANAS1Response(
            model_version=self.MODEL_VERSION,
            study_id=study_id,
            epochs=epoch_results,
            depression_severity_score=depression_score,
            depression_risk_level=risk_level,
            frontal_alpha_asymmetry=session_faa,
            biomarkers=biomarkers,
            clinical_flags=clinical_flags,
            background_rhythm=background_rhythm,
            clinical_impression=clinical_impression,
            processing_time_ms=processing_time_ms,
        )

    def _analyze_epoch(
        self,
        epoch_data: np.ndarray,
        epoch_index: int,
        start_time_sec: float,
        epoch_duration_sec: float,
        band_powers: dict,
        dominant_freq: float,
        channel_names: list[str],
        base_severity: float,
        rng: np.random.Generator,
        sample_rate: int,
    ) -> EpochAnalysis:
        # Per-channel band powers
        per_ch_powers = compute_band_powers_per_channel(epoch_data, sample_rate, channel_names)
        faa = compute_frontal_alpha_asymmetry(per_ch_powers, channel_names)

        # Depression contribution: weighted combination of biomarkers + mock noise
        # Negative FAA → depression; high theta/beta → depression; low alpha → depression
        alpha = band_powers.get("alpha", 0.3)
        theta = band_powers.get("theta", 0.2)
        beta = band_powers.get("beta", 0.2)

        faa_component = float(np.clip(-faa * 2, -1, 1))  # negative FAA → positive component
        alpha_suppression = float(np.clip(1.0 - alpha * 3, 0, 1))  # low alpha → high contribution
        theta_beta_elevation = float(np.clip((theta / max(beta, 0.01) - 1.0) * 0.5, 0, 1))

        raw_contribution = (
            0.35 * faa_component +
            0.25 * alpha_suppression +
            0.20 * theta_beta_elevation +
            0.20 * base_severity
        )
        noise = rng.normal(0, 0.05)
        depression_contribution = float(np.clip(raw_contribution + noise, 0.0, 1.0))

        # Artifact detection (transient jump detection)
        diff = np.abs(np.diff(epoch_data, axis=1))
        max_jump = float(np.max(diff)) if diff.size > 0 else 0.0
        median_jump = float(np.median(diff)) + 1e-8
        artifact_prob = float(np.clip((max_jump / median_jump - 50) / 200, 0.0, 1.0))

        # Channel attention: frontal-weighted for depression
        channel_attention = self._generate_channel_attention(
            epoch_data, channel_names, base_severity > 0.3, rng
        )

        # Confidence
        dist_from_boundary = abs(depression_contribution - 0.5)
        confidence = float(np.clip(0.6 + dist_from_boundary * 0.7, 0.0, 1.0))

        return EpochAnalysis(
            epoch_index=epoch_index,
            start_time_sec=start_time_sec,
            end_time_sec=start_time_sec + epoch_duration_sec,
            depression_contribution=depression_contribution,
            artifact_probability=artifact_prob,
            channel_attention=channel_attention,
            dominant_frequency_hz=dominant_freq,
            band_powers=band_powers,
            per_channel_powers=per_ch_powers,
            frontal_alpha_asymmetry=faa,
            confidence=confidence,
        )

    def _generate_channel_attention(
        self,
        epoch_data: np.ndarray,
        channel_names: list[str],
        is_depressed: bool,
        rng: np.random.Generator,
    ) -> dict[str, float]:
        variance = np.var(epoch_data, axis=1)
        weights = variance / (variance.sum() + 1e-8)

        if is_depressed:
            for i, ch in enumerate(channel_names):
                if ch in FRONTAL_CHANNELS:
                    weights[i] *= rng.uniform(2.5, 5.0)

        weights = weights / (weights.sum() + 1e-8)
        return {ch: float(w) for ch, w in zip(channel_names, weights)}

    def _generate_clinical_flags(
        self,
        epochs: list[EpochAnalysis],
        biomarkers: BiomarkerSummary,
        session_faa: float,
    ) -> list[ClinicalFlag]:
        flags: list[ClinicalFlag] = []
        duration = epochs[-1].end_time_sec if epochs else 0.0

        if session_faa < -0.1:
            severity = "HIGH" if session_faa < -0.3 else "MEDIUM"
            flags.append(ClinicalFlag(
                flag_type="FRONTAL_ASYMMETRY",
                severity=severity,
                onset_sec=0.0,
                duration_sec=duration,
                channels_involved=["F3", "F4", "Fp1", "Fp2"],
                description=(
                    f"Significant frontal alpha asymmetry detected (FAA = {session_faa:.3f}). "
                    f"Left frontal alpha suppression is a validated biomarker for depressive states."
                ),
            ))

        if biomarkers.alpha_power < 0.20:
            flags.append(ClinicalFlag(
                flag_type="ALPHA_SUPPRESSION",
                severity="MEDIUM",
                onset_sec=0.0,
                duration_sec=duration,
                channels_involved=["O1", "O2", "P3", "P4"],
                description=(
                    f"Reduced overall alpha power ({biomarkers.alpha_power:.0%}). "
                    f"Alpha suppression is associated with increased rumination and depressive cognition."
                ),
            ))

        if biomarkers.theta_beta_ratio > 2.0:
            flags.append(ClinicalFlag(
                flag_type="DEPRESSIVE_PATTERN",
                severity="MEDIUM",
                onset_sec=0.0,
                duration_sec=duration,
                channels_involved=["Fz", "Cz", "F3", "F4"],
                description=(
                    f"Elevated theta/beta ratio ({biomarkers.theta_beta_ratio:.2f}). "
                    f"This pattern suggests cortical hypoarousal consistent with depressive states."
                ),
            ))

        if biomarkers.delta_power > 0.35:
            flags.append(ClinicalFlag(
                flag_type="SLEEP_DISRUPTION",
                severity="LOW",
                onset_sec=0.0,
                duration_sec=duration,
                channels_involved=[],
                description=(
                    f"Excess delta activity ({biomarkers.delta_power:.0%}). "
                    f"May indicate sleep disruption or excessive daytime sleepiness, "
                    f"commonly associated with depressive episodes."
                ),
            ))

        return flags

    def _average_band_powers(self, band_powers_list: list[dict]) -> dict[str, float]:
        if not band_powers_list:
            return {}
        keys = band_powers_list[0].keys()
        return {k: float(np.mean([bp.get(k, 0) for bp in band_powers_list])) for k in keys}

    def _infer_background_rhythm(self, avg_band_powers: dict) -> str:
        alpha = avg_band_powers.get("alpha", 0)
        delta = avg_band_powers.get("delta", 0)
        theta = avg_band_powers.get("theta", 0)

        if alpha > 0.30:
            return "Well-organised posterior alpha rhythm (9–11 Hz)"
        elif delta > 0.30:
            return "Diffuse cerebral slowing with excess delta activity"
        elif theta > 0.30:
            return "Mild diffuse slowing with excess theta activity"
        else:
            return "Low-voltage fast activity; background mildly disorganised"

    def _generate_clinical_impression(
        self,
        flags: list[ClinicalFlag],
        depression_score: float,
        risk_level: str,
        background_rhythm: str,
        biomarkers: BiomarkerSummary,
    ) -> str:
        lines = [f"Background: {background_rhythm}."]

        lines.append(
            f"Depression severity score: {depression_score:.1f}/27 "
            f"(PHQ-9 equivalent: {risk_level})."
        )

        if biomarkers.frontal_alpha_asymmetry < -0.1:
            lines.append(
                f"Frontal alpha asymmetry (FAA = {biomarkers.frontal_alpha_asymmetry:.3f}) "
                f"indicates left frontal hypoactivation, a validated EEG biomarker for depression."
            )

        asymmetry_flags = [f for f in flags if f.flag_type == "FRONTAL_ASYMMETRY"]
        pattern_flags = [f for f in flags if f.flag_type == "DEPRESSIVE_PATTERN"]

        if asymmetry_flags or pattern_flags:
            lines.append(
                f"EEG biomarkers suggest {risk_level.lower()} depressive pattern. "
                f"Alpha/beta ratio: {biomarkers.alpha_beta_ratio:.2f}, "
                f"Theta/beta ratio: {biomarkers.theta_beta_ratio:.2f}."
            )

        if depression_score < 5:
            lines.append(
                "EEG biomarker profile is within normal range. "
                "No significant indicators of depressive pathology."
            )
        elif depression_score < 10:
            lines.append(
                "Mild EEG biomarker changes noted. Clinical correlation with "
                "standardised questionnaires (PHQ-9, BDI-II) recommended."
            )
        else:
            lines.append(
                "Significant EEG biomarker changes consistent with depressive pattern. "
                "Recommend clinical assessment and monitoring. "
                "Consider longitudinal EEG tracking to evaluate treatment response."
            )

        lines.append(
            "IMPORTANT: This is an AI-assisted depression screening tool. All findings "
            "require review and confirmation by a qualified psychiatrist or neurologist. "
            "EEG biomarkers should be interpreted alongside clinical interview and "
            "standardised rating scales."
        )

        return " ".join(lines)
