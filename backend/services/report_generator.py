from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schemas.analysis import AnalysisResultFull
from models.study import Study
from models.patient import Patient


class ReportGenerator:
    def __init__(self):
        template_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def generate_json_report(
        self,
        analysis: AnalysisResultFull,
        study: Study,
        patient: Patient,
    ) -> dict:
        top_epochs = sorted(analysis.epochs, key=lambda e: e.seizure_probability, reverse=True)[:10]

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "patient": {
                "name": patient.name,
                "mrn": patient.mrn,
                "date_of_birth": str(patient.date_of_birth),
                "gender": patient.gender,
                "referring_physician": patient.referring_physician,
            },
            "study": {
                "id": study.id,
                "date": study.study_date.strftime("%d %B %Y, %H:%M"),
                "duration_sec": study.recording_duration_sec,
                "sample_rate_hz": study.sample_rate_hz,
                "channel_count": study.channel_count,
                "is_synthetic": study.is_synthetic,
            },
            "ai_analysis": {
                "model_version": analysis.model_version,
                "overall_seizure_probability": analysis.overall_seizure_probability,
                "overall_seizure_probability_pct": f"{analysis.overall_seizure_probability:.0%}",
                "background_rhythm": analysis.background_rhythm,
                "clinical_impression": analysis.clinical_impression,
                "processing_time_ms": analysis.processing_time_ms,
                "risk_level": (
                    "HIGH" if analysis.overall_seizure_probability >= 0.6
                    else "MODERATE" if analysis.overall_seizure_probability >= 0.35
                    else "LOW"
                ),
            },
            "clinical_flags": [
                {
                    "flag_type": f.flag_type,
                    "severity": f.severity,
                    "onset_sec": f.onset_sec,
                    "onset_formatted": _format_time(f.onset_sec),
                    "duration_sec": f.duration_sec,
                    "channels_involved": ", ".join(f.channels_involved) if f.channels_involved else "—",
                    "description": f.description,
                }
                for f in analysis.clinical_flags
            ],
            "top_epochs": [
                {
                    "epoch_index": ep.epoch_index,
                    "start_formatted": _format_time(ep.start_time_sec),
                    "end_formatted": _format_time(ep.end_time_sec),
                    "seizure_probability_pct": f"{ep.seizure_probability:.0%}",
                    "dominant_frequency_hz": f"{ep.dominant_frequency_hz:.1f}",
                    "top_channels": ", ".join(
                        sorted(ep.channel_attention, key=ep.channel_attention.get, reverse=True)[:3]
                    ),
                }
                for ep in top_epochs
            ],
            "total_epochs": len(analysis.epochs),
        }

    def generate_html_report(self, report_data: dict) -> str:
        template = self.env.get_template("report.html")
        return template.render(**report_data)


def _format_time(sec: float) -> str:
    minutes = int(sec) // 60
    seconds = int(sec) % 60
    return f"{minutes:02d}:{seconds:02d}"
