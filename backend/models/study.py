from datetime import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    study_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    recording_duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    sample_rate_hz: Mapped[int] = mapped_column(Integer, default=256)
    channel_count: Mapped[int] = mapped_column(Integer, default=0)
    channel_names: Mapped[str] = mapped_column(String(1000), default="[]")  # JSON list
    file_path: Mapped[str] = mapped_column(String(500), default="")
    display_data_path: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(
        String(30), default="uploaded"
    )  # uploaded | preprocessing | analyzing | complete | error
    error_message: Mapped[str] = mapped_column(String(500), default="")
    is_synthetic: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped["Patient"] = relationship("Patient", back_populates="studies")  # noqa: F821
    analysis: Mapped["AnalysisResult"] = relationship(  # noqa: F821
        "AnalysisResult", back_populates="study", uselist=False, cascade="all, delete-orphan"
    )
    epoch_progress: Mapped[int] = mapped_column(Integer, default=0)
    epoch_total: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[str] = mapped_column(String(20), default="edf")  # edf | synthetic | pdf
    original_filename: Mapped[str] = mapped_column(String(200), default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")  # markdown extracted from PDF
