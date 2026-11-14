from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    production_line: Mapped[str] = mapped_column(String(80))
    inspections: Mapped[list["Inspection"]] = relationship(back_populates="batch")


class AIClassification(Base):
    __tablename__ = "ai_classifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_ref: Mapped[str] = mapped_column(String(500))
    predicted_defect_type: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100))
    inspector: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    inspection: Mapped["Inspection | None"] = relationship(back_populates="classification", uselist=False)


class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    classification_id: Mapped[int] = mapped_column(ForeignKey("ai_classifications.id"), unique=True)
    final_defect_type: Mapped[str] = mapped_column(String(40), index=True)
    was_overridden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspector: Mapped[str] = mapped_column(String(120))
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    batch: Mapped[Batch] = relationship(back_populates="inspections")
    classification: Mapped[AIClassification] = relationship(back_populates="inspection", lazy="joined")

    @property
    def image_ref(self):
        return self.classification.image_ref

    @property
    def ai_predicted_defect_type(self):
        return self.classification.predicted_defect_type

    @property
    def ai_confidence(self):
        return self.classification.confidence
