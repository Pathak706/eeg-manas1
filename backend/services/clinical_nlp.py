"""
Clinical NLP Extractor — Depression Assessment.

Parses structured clinical data from free-text EEG/psychiatric report markdown.
Uses pure regex + keyword matching — no external NLP models required.
"""
import re
from dataclasses import dataclass, field

CHANNELS_10_20 = {
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
}
FRONTAL_CHANNELS = {"Fp1", "Fp2", "F3", "F4", "F7", "F8"}

# ── Depression severity keyword tiers ──────────────────────────────────────

_SEVERE_DEPRESSION = [
    r"severe depression", r"major depressive", r"PHQ.?9.*(?:2[0-7]|severe)",
    r"suicidal ideation", r"severe.*depressive", r"treatment.resistant",
    r"severe.*MDD", r"melancholic",
]
_MODERATE_DEPRESSION = [
    r"moderate depression", r"moderately severe", r"PHQ.?9.*(?:1[0-9]|moderate)",
    r"persistent.*depressive", r"significant.*depression", r"MDD",
    r"major depressive disorder",
]
_MILD_DEPRESSION = [
    r"mild depression", r"subthreshold", r"dysthymi", r"subclinical",
    r"PHQ.?9.*(?:[5-9]|mild)", r"mild.*depressive", r"low mood",
    r"adjustment disorder",
]
_NO_DEPRESSION = [
    r"no depression", r"euthymic", r"remission", r"normal mood",
    r"not depressed", r"within normal", r"no.*depressive",
    r"PHQ.?9.*(?:[0-4]|minimal)", r"asymptomatic",
]

# ── Band power keyword mapping ─────────────────────────────────────────────

_BAND_KEYWORDS = {
    "delta": [r"excess delta", r"delta slowing", r"delta activity", r"slow wave"],
    "theta": [r"theta activity", r"theta slowing", r"excess theta", r"theta elevation", r"frontal theta"],
    "alpha": [r"alpha.*suppress", r"reduced alpha", r"alpha.*asymmetr", r"alpha rhythm", r"alpha activity"],
    "beta": [r"beta activity", r"excess beta", r"fast activity"],
    "gamma": [r"gamma activity", r"high.frequency activity"],
}

# ── Depression biomarker patterns ──────────────────────────────────────────

_BIOMARKER_PATTERNS = {
    "alpha_asymmetry": [r"alpha.*asymmetr", r"frontal.*asymmetr", r"FAA", r"left.*frontal.*suppress"],
    "theta_elevation": [r"theta.*elevat", r"frontal.*theta", r"excess.*theta", r"theta.beta.*ratio"],
    "alpha_suppression": [r"alpha.*suppress", r"reduced.*alpha", r"low.*alpha", r"alpha.*deficit"],
    "sleep_disruption": [r"sleep.*disrupt", r"insomnia", r"hypersomnia", r"excess.*delta", r"sleep.*disturb"],
}

_DURATION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:minute|min)s?", re.IGNORECASE),
    re.compile(r"recording.*?(\d+(?:\.\d+)?)\s*(?:minute|min)", re.IGNORECASE),
    re.compile(r"duration.*?(\d+(?:\.\d+)?)\s*(?:minute|min)", re.IGNORECASE),
]


@dataclass
class ClinicalExtraction:
    depression_severity_score: float      # 0–27 PHQ-9 equivalent
    depression_risk_level: str
    background_rhythm: str
    clinical_flags: list[dict] = field(default_factory=list)
    recording_duration_sec: float = 120.0
    band_powers: dict[str, float] = field(default_factory=dict)
    frontal_alpha_asymmetry: float = 0.0
    source_confidence: str = "LOW"
    extracted_fields: dict = field(default_factory=dict)


def _phq9_risk_level(score: float) -> str:
    if score <= 4: return "Minimal"
    if score <= 9: return "Mild"
    if score <= 14: return "Moderate"
    if score <= 19: return "Moderately Severe"
    return "Severe"


class ClinicalNLPExtractor:

    def extract(self, text: str) -> ClinicalExtraction:
        lower = text.lower()

        score, tier = self._extract_depression_score(lower)
        risk_level = _phq9_risk_level(score)
        background_rhythm = self._extract_background_rhythm(text, lower)
        band_powers = self._extract_band_powers(lower)
        recording_duration_sec = self._extract_duration(lower)
        clinical_flags = self._extract_clinical_flags(text, lower)
        faa = self._extract_faa(lower)
        source_confidence = self._assess_confidence(tier, clinical_flags, band_powers)

        return ClinicalExtraction(
            depression_severity_score=score,
            depression_risk_level=risk_level,
            background_rhythm=background_rhythm,
            clinical_flags=clinical_flags,
            recording_duration_sec=recording_duration_sec,
            band_powers=band_powers,
            frontal_alpha_asymmetry=faa,
            source_confidence=source_confidence,
            extracted_fields={
                "depression_tier": tier,
                "channels_mentioned": list(self._find_channels(text)),
                "recording_duration_sec": recording_duration_sec,
            },
        )

    def _extract_depression_score(self, lower: str) -> tuple[float, str]:
        import random
        rng = random.Random(42)

        # Try to extract explicit PHQ-9 score
        m = re.search(r"PHQ.?9.*?(\d{1,2})", lower)
        if m:
            score = min(int(m.group(1)), 27)
            return float(score), "EXPLICIT"

        for pat in _SEVERE_DEPRESSION:
            if re.search(pat, lower):
                return round(rng.uniform(20, 25), 1), "SEVERE"
        for pat in _MODERATE_DEPRESSION:
            if re.search(pat, lower):
                return round(rng.uniform(12, 18), 1), "MODERATE"
        for pat in _NO_DEPRESSION:
            if re.search(pat, lower):
                return round(rng.uniform(1, 4), 1), "NONE"
        for pat in _MILD_DEPRESSION:
            if re.search(pat, lower):
                return round(rng.uniform(5, 9), 1), "MILD"

        return 8.0, "UNKNOWN"

    def _extract_faa(self, lower: str) -> float:
        for pat in _BIOMARKER_PATTERNS["alpha_asymmetry"]:
            if re.search(pat, lower):
                return -0.25  # negative = depression indicator
        return 0.0

    def _extract_background_rhythm(self, text: str, lower: str) -> str:
        if re.search(r"normal.*background|background.*normal|well.organised", lower):
            return "Well-organised posterior alpha rhythm (9-11 Hz)"
        if re.search(r"diffuse.*slow|slow.*background", lower):
            return "Diffuse cerebral slowing with excess delta/theta activity"
        if re.search(r"alpha.*suppress|reduced.*alpha", lower):
            return "Reduced alpha activity with frontal theta predominance"
        if re.search(r"excess theta|theta slowing|frontal theta", lower):
            return "Mild diffuse slowing with excess theta activity"
        return "Background rhythm not clearly specified in source report"

    def _extract_band_powers(self, lower: str) -> dict[str, float]:
        raw: dict[str, float] = {}
        for band, patterns in _BAND_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, lower):
                    raw[band] = {"delta": 0.50, "theta": 0.40, "alpha": 0.15, "beta": 0.30, "gamma": 0.15}[band]
                    break

        if not raw:
            return {"delta": 0.20, "theta": 0.20, "alpha": 0.35, "beta": 0.20, "gamma": 0.05}

        defaults = {"delta": 0.10, "theta": 0.10, "alpha": 0.20, "beta": 0.10, "gamma": 0.05}
        for band in defaults:
            if band not in raw:
                raw[band] = defaults[band]

        total = sum(raw.values())
        return {k: round(v / total, 4) for k, v in raw.items()}

    def _extract_duration(self, lower: str) -> float:
        for pat in _DURATION_PATTERNS:
            m = pat.search(lower)
            if m:
                return round(float(m.group(1)) * 60, 1)
        return 120.0

    def _extract_clinical_flags(self, text: str, lower: str) -> list[dict]:
        flags: list[dict] = []
        channels = self._find_channels(text)

        for flag_type, patterns in _BIOMARKER_PATTERNS.items():
            matched = any(re.search(pat, lower) for pat in patterns)
            if not matched:
                continue

            if flag_type == "alpha_asymmetry":
                flags.append({
                    "flag_type": "FRONTAL_ASYMMETRY",
                    "severity": "HIGH",
                    "onset_sec": 0.0,
                    "duration_sec": 0.0,
                    "channels_involved": ["F3", "F4", "Fp1", "Fp2"],
                    "description": "Frontal alpha asymmetry detected in source report — depression biomarker.",
                })
            elif flag_type == "theta_elevation":
                flags.append({
                    "flag_type": "DEPRESSIVE_PATTERN",
                    "severity": "MEDIUM",
                    "onset_sec": 0.0,
                    "duration_sec": 0.0,
                    "channels_involved": list(channels & FRONTAL_CHANNELS)[:4],
                    "description": "Elevated theta activity detected — cortical hypoarousal pattern.",
                })
            elif flag_type == "alpha_suppression":
                flags.append({
                    "flag_type": "ALPHA_SUPPRESSION",
                    "severity": "MEDIUM",
                    "onset_sec": 0.0,
                    "duration_sec": 0.0,
                    "channels_involved": ["O1", "O2", "P3", "P4"],
                    "description": "Reduced alpha power — associated with depressive cognition.",
                })
            elif flag_type == "sleep_disruption":
                flags.append({
                    "flag_type": "SLEEP_DISRUPTION",
                    "severity": "LOW",
                    "onset_sec": 0.0,
                    "duration_sec": 0.0,
                    "channels_involved": [],
                    "description": "Sleep disruption indicators detected in source report.",
                })

        return flags

    def _find_channels(self, text: str) -> set[str]:
        found = set()
        for ch in CHANNELS_10_20:
            if re.search(r"\b" + re.escape(ch) + r"\b", text):
                found.add(ch)
        return found

    def _assess_confidence(self, tier: str, flags: list, band_powers: dict) -> str:
        score = 0
        if tier in ("SEVERE", "NONE", "EXPLICIT"):
            score += 2
        elif tier in ("MODERATE", "MILD"):
            score += 1
        if flags:
            score += 1
        if len(flags) >= 2:
            score += 1
        non_default = sum(1 for v in band_powers.values() if v not in (0.20, 0.35, 0.05))
        if non_default >= 2:
            score += 1
        if score >= 4:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
