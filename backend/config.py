"""
config.py — Centralised configuration via Pydantic Settings.

All values are read from environment variables (or a .env file).
Import `settings` everywhere — never import os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google Sheets ──────────────────────────────────────────────────────
    google_sheet_url: str = Field("", description="Full URL of the Google Sheet (set in .env)")
    google_sheet_worksheet: str = Field("Sheet1", description="Worksheet/tab name")

    # ── Groq ───────────────────────────────────────────────────────────────
    groq_api_key: str = Field("", description="Groq API key (set in .env)")
    groq_model: str = Field("llama-3.3-70b-versatile")

    # ── Android Gateway ────────────────────────────────────────────────────
    android_gateway_host: str = Field("192.168.1.100")
    android_gateway_port: int = Field(8765)

    @property
    def android_gateway_ws_url(self) -> str:
        return f"ws://{self.android_gateway_host}:{self.android_gateway_port}"

    # ── Speech-to-Text ─────────────────────────────────────────────────────
    whisper_model: str = Field("large-v3")
    whisper_device: str = Field("cpu")
    # L003: Hindi needs 900ms silence window — exposed as env var
    vad_silence_ms: int = Field(900)

    # ── Text-to-Speech ─────────────────────────────────────────────────────
    piper_voice: str = Field("hi_IN-hemant-medium")
    piper_model_path: str = Field("models/hi_IN-hemant-medium.onnx")

    # ── Audio ──────────────────────────────────────────────────────────────
    # L001: speakerphone is the only non-root option on Android 10+
    audio_strategy: str = Field("speakerphone")

    # ── Call Behaviour ─────────────────────────────────────────────────────
    call_ring_timeout_sec: int = Field(45)
    inter_call_delay_min_sec: int = Field(30)
    inter_call_delay_max_sec: int = Field(120)
    max_conversation_turns: int = Field(20)

    # ── Recording ──────────────────────────────────────────────────────────
    recording_enabled: bool = Field(True)
    recording_format: str = Field("mp3")
    recordings_dir: str = Field("recordings")

    # ── Server ─────────────────────────────────────────────────────────────
    server_host: str = Field("0.0.0.0")
    server_port: int = Field(8000)

    # ── Session DB ─────────────────────────────────────────────────────────
    session_db_path: str = Field("data/sessions.db")


# Singleton — import this everywhere
settings = Settings()
