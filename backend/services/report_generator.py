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
        top_epochs = sorted(analysis.epochs, key=lambda e: e.depression_contribution, reverse=True)[:10]

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
                "depression_severity_score": analysis.depression_severity_score,
                "depression_severity_display": f"{analysis.depression_severity_score:.1f}/27",
                "depression_risk_level": analysis.depression_risk_level,
                "frontal_alpha_asymmetry": f"{analysis.frontal_alpha_asymmetry:.3f}",
                "background_rhythm": analysis.background_rhythm,
                "clinical_impression": analysis.clinical_impression,
                "processing_time_ms": analysis.processing_time_ms,
            },
            "biomarkers": {
                "alpha_power": f"{analysis.biomarkers.alpha_power:.0%}",
                "beta_power": f"{analysis.biomarkers.beta_power:.0%}",
                "theta_power": f"{analysis.biomarkers.theta_power:.0%}",
                "delta_power": f"{analysis.biomarkers.delta_power:.0%}",
                "gamma_power": f"{analysis.biomarkers.gamma_power:.0%}",
                "frontal_alpha_asymmetry": f"{analysis.biomarkers.frontal_alpha_asymmetry:.3f}",
                "alpha_beta_ratio": f"{analysis.biomarkers.alpha_beta_ratio:.2f}",
                "theta_beta_ratio": f"{analysis.biomarkers.theta_beta_ratio:.2f}",
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
                    "depression_contribution_pct": f"{ep.depression_contribution:.0%}",
                    "dominant_frequency_hz": f"{ep.dominant_frequency_hz:.1f}",
                    "faa": f"{ep.frontal_alpha_asymmetry:.3f}",
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
