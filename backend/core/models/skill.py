import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.postgres import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # technical | tool | methodology | soft
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    subdomain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    low_confidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | complete | failed
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job_postings: Mapped[list["JobPostingSkill"]] = relationship(
        "JobPostingSkill", back_populates="skill", lazy="select"
    )


class JobPostingSkill(Base):
    __tablename__ = "job_posting_skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="job_postings")
