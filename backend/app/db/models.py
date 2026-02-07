"""
最小可用数据模型：domains, documents, chunks, prompt_versions, usage_logs, ratings, limits。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    source_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    group_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    token_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Rating(Base):
    __tablename__ = "ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[int] = mapped_column(ForeignKey("usage_logs.id"), nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)  # good | normal | bad
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LimitConfig(Base):
    __tablename__ = "limits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)  # user | group | global
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
