import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.postgres import Base


class SurveySession(Base):
    __tablename__ = "survey_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="created", nullable=False, index=True
    )  # created | active | completing | completed | abandoned
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User | None"] = relationship("User", back_populates="survey_sessions")
    messages: Mapped[list["SurveyMessage"]] = relationship(
        "SurveyMessage", back_populates="session", order_by="SurveyMessage.created_at", lazy="select"
    )
    extraction: Mapped["SurveyExtraction | None"] = relationship(
        "SurveyExtraction", back_populates="session", uselist=False, lazy="select"
    )


class SurveyMessage(Base):
    __tablename__ = "survey_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("survey_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["SurveySession"] = relationship("SurveySession", back_populates="messages")


class SurveyExtraction(Base):
    __tablename__ = "survey_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("survey_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    self_reported_role: Mapped[str | None] = mapped_column(String(500), nullable=True)
    self_reported_domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classified_domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_anxiety_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    upskilling_goals: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    key_themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_llm_extraction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["SurveySession"] = relationship("SurveySession", back_populates="extraction")
