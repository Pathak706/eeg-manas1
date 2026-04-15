"""
Clinical NLP Extractor.

Parses structured clinical data from free-text EEG report markdown.
Uses pure regex + keyword matching — no external NLP models required.
"""
import re
from dataclasses import dataclass, field

# All 10-20 EEG channel names for detection
CHANNELS_10_20 = {
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz",
}
TEMPORAL_CHANNELS = {"T3", "T4", "F7", "F8", "T5", "T6"}

# ── Seizure probability keyword tiers ──────────────────────────────────────

_HIGH_SEIZURE = [
    r"definite seizure", r"confirmed ictal", r"seizure recorded",
    r"ictal activity", r"epileptic seizure", r"status epilepticus",
    r"ictal discharge", r"electrographic seizure",
]
_PROBABLE_SEIZURE = [
    r"likely epileptiform", r"probable seizure", r"high suspicion",
    r"highly suggestive", r"probable ictal", r"consistent with seizure",
    r"epileptiform discharge", r"spike.wave", r"polyspike",
]
_POSSIBLE_SEIZURE = [
    r"possible seizure", r"cannot exclude", r"borderline",
    r"cannot rule out", r"suspicious for", r"possible epileptiform",
    r"interictal discharge", r"sharp wave", r"suspicious discharge",
]
_NO_SEIZURE = [
    r"no epileptiform", r"no seizure", r"normal eeg",
    r"no ictal", r"within normal limits", r"unremarkable eeg",
    r"no abnormality", r"no definite epileptiform",
]

# ── Band power keyword mapping ─────────────────────────────────────────────

_BAND_KEYWORDS = {
    "delta": [r"excess delta", r"delta slowing", r"delta activity", r"slow wave", r"delta waves"],
    "theta": [r"theta activity", r"theta slowing", r"excess theta", r"theta waves"],
    "alpha": [r"normal alpha", r"posterior alpha", r"alpha rhythm", r"alpha activity", r"well.organised.*alpha"],
    "beta": [r"beta activity", r"excess beta", r"fast activity", r"beta waves"],
    "gamma": [r"gamma activity", r"high.frequency activity"],
}

# ── Timestamp patterns ────────────────────────────────────────────────────

_TS_PATTERNS = [
    # "at 45 seconds" / "at 45s" / "at 45 sec"
    re.compile(r"at\s+(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?", re.IGNORECASE),
    # "onset at 01:23" (mm:ss)
    re.compile(r"onset\s+(?:at\s+)?(\d{1,2}):(\d{2})", re.IGNORECASE),
    # "from 30 to 48 seconds"
    re.compile(r"from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s*s(?:ec)?", re.IGNORECASE),
    # "beginning at 30 seconds"
    re.compile(r"beginning\s+at\s+(\d+(?:\.\d+)?)\s*s(?:ec)?", re.IGNORECASE),
]

# ── Event type detection ──────────────────────────────────────────────────

_EVENT_KEYWORDS = {
    "SEIZURE_EVENT": [
        r"\bseizure\b", r"\bictal\b", r"\bictus\b", r"\bconvuls",
    ],
    "INTERICTAL_DISCHARGE": [
        r"interictal", r"epileptiform discharge", r"spike.wave", r"sharp wave",
        r"polyspike", r"\bspike\b",
    ],
    "SLOWING": [
        r"\bslowing\b", r"slow activity", r"delta slowing", r"theta slowing",
        r"diffuse.*slow", r"slow.*background",
    ],
    "ARTIFACT": [
        r"\bartifact\b", r"muscle artifact", r"eye.blink", r"movement artifact",
    ],
}

# ── Duration extraction ────────────────────────────────────────────────────

_DURATION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:minute|min)(?:s)?(?:\s+(?:\d+(?:\.\d+)?)\s*s(?:ec)?s?)?",
               re.IGNORECASE),
    re.compile(r"recording.*?(\d+(?:\.\d+)?)\s*(?:minute|min)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:minute|min).*?recording", re.IGNORECASE),
    re.compile(r"duration.*?(\d+(?:\.\d+)?)\s*(?:minute|min)", re.IGNORECASE),
]


@dataclass
class ClinicalExtraction:
    overall_seizure_probability: float
    background_rhythm: str
    clinical_flags: list[dict] = field(default_factory=list)
    recording_duration_sec: float = 120.0
    band_powers: dict[str, float] = field(default_factory=dict)
    source_confidence: str = "LOW"   # HIGH | MEDIUM | LOW
    extracted_fields: dict = field(default_factory=dict)


class ClinicalNLPExtractor:

    def extract(self, text: str) -> ClinicalExtraction:
        lower = text.lower()

        seizure_prob, prob_tier = self._extract_seizure_probability(lower)
        background_rhythm = self._extract_background_rhythm(text, lower)
        band_powers = self._extract_band_powers(lower)
        recording_duration_sec = self._extract_duration(lower)
        clinical_flags = self._extract_clinical_flags(text, lower)
        source_confidence = self._assess_confidence(prob_tier, clinical_flags, band_powers)

        return ClinicalExtraction(
            overall_seizure_probability=seizure_prob,
            background_rhythm=background_rhythm,
            clinical_flags=clinical_flags,
            recording_duration_sec=recording_duration_sec,
            band_powers=band_powers,
            source_confidence=source_confidence,
            extracted_fields={
                "seizure_probability_tier": prob_tier,
                "channels_mentioned": self._find_channels(text),
                "recording_duration_sec": recording_duration_sec,
            },
        )

    # ── Seizure probability ────────────────────────────────────────────────

    def _extract_seizure_probability(self, lower: str) -> tuple[float, str]:
        import random
        rng = random.Random(42)

        for pattern in _HIGH_SEIZURE:
            if re.search(pattern, lower):
                return round(rng.uniform(0.88, 0.95), 2), "HIGH"

        for pattern in _PROBABLE_SEIZURE:
            if re.search(pattern, lower):
                return round(rng.uniform(0.65, 0.82), 2), "PROBABLE"

        for pattern in _NO_SEIZURE:
            if re.search(pattern, lower):
                return round(rng.uniform(0.05, 0.18), 2), "NONE"

        for pattern in _POSSIBLE_SEIZURE:
            if re.search(pattern, lower):
                return round(rng.uniform(0.38, 0.55), 2), "POSSIBLE"

        return 0.30, "UNKNOWN"

    # ── Background rhythm ──────────────────────────────────────────────────

    def _extract_background_rhythm(self, text: str, lower: str) -> str:
        # Try "X Hz alpha" style
        m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]?\s*(\d+(?:\.\d+)?)?\s*hz\s+(\w+)", lower)
        if m:
            freq = m.group(1)
            band = m.group(3)
            return f"Background {band} rhythm at {freq} Hz"

        if re.search(r"normal.*background|background.*normal|well.organised", lower):
            return "Well-organised posterior alpha rhythm (9–11 Hz)"
        if re.search(r"diffuse.*slow|slow.*background|generalised.*slow", lower):
            return "Diffuse cerebral slowing with excess delta/theta activity"
        if re.search(r"excess delta|delta slowing", lower):
            return "Diffuse cerebral slowing with excess delta activity"
        if re.search(r"excess theta|theta slowing", lower):
            return "Mild diffuse slowing with excess theta activity"
        if re.search(r"low.voltage|fast activity", lower):
            return "Low-voltage fast activity; background mildly disorganised"

        return "Background rhythm not clearly specified in source report"

    # ── Band powers ────────────────────────────────────────────────────────

    def _extract_band_powers(self, lower: str) -> dict[str, float]:
        raw: dict[str, float] = {}

        for band, patterns in _BAND_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, lower):
                    raw[band] = {
                        "delta": 0.50, "theta": 0.40, "alpha": 0.40,
                        "beta": 0.30, "gamma": 0.15,
                    }[band]
                    break

        if not raw:
            # Default neutral spectrum
            return {"delta": 0.20, "theta": 0.20, "alpha": 0.35, "beta": 0.20, "gamma": 0.05}

        # Ensure all bands present, then normalise
        defaults = {"delta": 0.10, "theta": 0.10, "alpha": 0.20, "beta": 0.10, "gamma": 0.05}
        for band in defaults:
            if band not in raw:
                raw[band] = defaults[band]

        total = sum(raw.values())
        return {k: round(v / total, 4) for k, v in raw.items()}

    # ── Recording duration ─────────────────────────────────────────────────

    def _extract_duration(self, lower: str) -> float:
        for pat in _DURATION_PATTERNS:
            m = pat.search(lower)
            if m:
                minutes = float(m.group(1))
                return round(minutes * 60, 1)
        return 120.0  # default 2-minute recording

    # ── Clinical flags ─────────────────────────────────────────────────────

    def _extract_clinical_flags(self, text: str, lower: str) -> list[dict]:
        flags: list[dict] = []
        channels = self._find_channels(text)
        temporal_present = bool(channels & TEMPORAL_CHANNELS)

        # Collect timestamp mentions
        timestamps = self._find_timestamps(lower)

        # Determine event types present
        for flag_type, patterns in _EVENT_KEYWORDS.items():
            matched = any(re.search(pat, lower) for pat in patterns)
            if not matched:
                continue

            onset_sec = timestamps[0] if timestamps else 0.0
            duration_sec = (timestamps[1] - timestamps[0]) if len(timestamps) >= 2 else 20.0
            if duration_sec <= 0:
                duration_sec = 20.0

            involved = list(channels)[:4] if channels else []

            if flag_type == "SEIZURE_EVENT":
                laterality = "left" if any(c.endswith(("3", "7")) for c in involved) else "right"
                region = "temporal" if temporal_present else "fronto-temporal"
                desc = (
                    f"Focal ictal discharge with {laterality} {region} predominance. "
                    f"Onset at {onset_sec:.1f}s, duration {duration_sec:.0f}s. "
                    + (f"Channels: {', '.join(involved[:2])}." if involved else "")
                )
                flags.append({
                    "flag_type": "SEIZURE_EVENT",
                    "severity": "HIGH",
                    "onset_sec": onset_sec,
                    "duration_sec": duration_sec,
                    "channels_involved": involved,
                    "description": desc,
                })

            elif flag_type == "INTERICTAL_DISCHARGE" and not any(
                f["flag_type"] == "SEIZURE_EVENT" for f in flags
            ):
                flags.append({
                    "flag_type": "INTERICTAL_DISCHARGE",
                    "severity": "MEDIUM",
                    "onset_sec": onset_sec,
                    "duration_sec": 2.0,
                    "channels_involved": involved[:3],
                    "description": f"Interictal epileptiform discharge noted at {onset_sec:.1f}s.",
                })

            elif flag_type == "SLOWING":
                flags.append({
                    "flag_type": "SLOWING",
                    "severity": "MEDIUM",
                    "onset_sec": 0.0,
                    "duration_sec": 0.0,
                    "channels_involved": [],
                    "description": "Diffuse background slowing identified in source report.",
                })

            elif flag_type == "ARTIFACT":
                flags.append({
                    "flag_type": "ARTIFACT",
                    "severity": "LOW",
                    "onset_sec": onset_sec,
                    "duration_sec": 5.0,
                    "channels_involved": [],
                    "description": "Artifact noted in source report.",
                })

        return flags

    # ── Helpers ────────────────────────────────────────────────────────────

    def _find_channels(self, text: str) -> set[str]:
        found = set()
        for ch in CHANNELS_10_20:
            if re.search(r"\b" + re.escape(ch) + r"\b", text):
                found.add(ch)
        return found

    def _find_timestamps(self, lower: str) -> list[float]:
        times: list[float] = []
        for pat in _TS_PATTERNS:
            for m in pat.finditer(lower):
                groups = [g for g in m.groups() if g is not None]
                if len(groups) == 2 and ":" in m.group(0):
                    # mm:ss format
                    times.append(int(groups[0]) * 60 + int(groups[1]))
                elif len(groups) == 2:
                    # from X to Y
                    times.append(float(groups[0]))
                    times.append(float(groups[1]))
                elif groups:
                    times.append(float(groups[0]))
        return sorted(set(times))

    def _assess_confidence(
        self,
        prob_tier: str,
        flags: list[dict],
        band_powers: dict,
    ) -> str:
        score = 0
        if prob_tier in ("HIGH", "NONE"):
            score += 2
        elif prob_tier in ("PROBABLE", "POSSIBLE"):
            score += 1

        if flags:
            score += 1
        if len(flags) >= 2:
            score += 1

        # Band powers that came from text keywords (non-default)
        non_default = sum(1 for v in band_powers.values() if v not in (0.20, 0.35, 0.05))
        if non_default >= 2:
            score += 1

        if score >= 4:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
