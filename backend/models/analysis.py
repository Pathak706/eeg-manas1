from datetime import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(50), default="manas1-mock-v0.1")
    overall_seizure_probability: Mapped[float] = mapped_column(Float, default=0.0)
    clinical_impression: Mapped[str] = mapped_column(String(2000), default="")
    background_rhythm: Mapped[str] = mapped_column(String(200), default="")
    clinical_flags: Mapped[str] = mapped_column(String(5000), default="[]")  # JSON list
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    study: Mapped["Study"] = relationship("Study", back_populates="analysis")  # noqa: F821
    epochs: Mapped[list["EpochResult"]] = relationship(
        "EpochResult", back_populates="analysis", cascade="all, delete-orphan",
        order_by="EpochResult.epoch_index"
    )


class EpochResult(Base):
    __tablename__ = "epoch_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"), index=True)
    epoch_index: Mapped[int] = mapped_column(Integer)
    start_time_sec: Mapped[float] = mapped_column(Float)
    end_time_sec: Mapped[float] = mapped_column(Float)
    seizure_probability: Mapped[float] = mapped_column(Float)
    artifact_probability: Mapped[float] = mapped_column(Float)
    channel_attention: Mapped[str] = mapped_column(String(2000), default="{}")  # JSON dict
    dominant_frequency_hz: Mapped[float] = mapped_column(Float, default=0.0)
    band_powers: Mapped[str] = mapped_column(String(500), default="{}")  # JSON dict
    confidence: Mapped[float] = mapped_column(Float, default=0.9)

    analysis: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="epochs")
