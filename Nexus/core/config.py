"""Immutable configuration loader with env precedence."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

from nexus.core.exceptions import ConfigurationError

SECRET_FIELD_KEYWORDS = ("api_key", "secret", "token", "password", "dsn")


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def _default_instance(cls: type) -> Any:
    """Return a plain default instance of a slots dataclass."""
    return cls()


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE, ignores comments)."""
    if not path.exists():
        return {}
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    wake_word: str = "nexus"
    wake_word_sensitivity: float = 0.55
    stt_model: str = "whisper-large-v3-turbo"
    stt_streaming: bool = True
    tts_provider: str = "elevenlabs"
    tts_voice_id: str = ""
    sample_rate_hz: int = 16_000
    vad_aggressiveness: float = 0.5


@dataclass(frozen=True, slots=True)
class LLMConfig:
    provider: str = "claude"
    model_name: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 2048
    temperature: float = 0.4
    request_timeout_s: float = 30.0


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    vector_db_provider: str = "qdrant"
    vector_db_url: str = "http://localhost:6333"
    postgres_dsn: str = ""
    knowledge_graph_enabled: bool = False
    neo4j_uri: str = ""
    short_term_max_turns: int = 40
    summary_every_n_turns: int = 20


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    blocked_package_substrings: tuple[str, ...] = (
        "com.google.android.apps.wallet",
        "com.paypal",
        "com.chase",
        "com.bankofamerica",
        "com.venmo",
        "com.squareup.cash",
        "com.coinbase",
    )
    confirm_required_actions: tuple[str, ...] = (
        "send_message",
        "make_call",
        "delete_app",
        "power_state",
        "delete_file",
        "deploy_code",
    )
    audit_log_path: str = "./data/audit/audit.log"
    encrypt_memory_at_rest: bool = True
    max_actions_per_minute: int = 20


@dataclass(frozen=True, slots=True)
class NexusConfig:
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_dir: str = "./data/logs"
    data_dir: str = "./data"
    supported_languages: tuple[str, ...] = ("en", "ne")
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    def redacted(self) -> dict[str, Any]:
        """Return a dict with secret fields masked."""
        def _redact_obj(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                res = {}
                for f in fields(obj):
                    val = getattr(obj, f.name)
                    is_secret = any(kw in f.name.lower() for kw in SECRET_FIELD_KEYWORDS)
                    if is_secret and val:
                        res[f.name] = "***REDACTED***"
                    else:
                        res[f.name] = _redact_obj(val)
                return res
            if isinstance(obj, (list, tuple, set)):
                return type(obj)(_redact_obj(v) for v in obj)
            if isinstance(obj, dict):
                return {_redact_obj(k): _redact_obj(v) for k, v in obj.items()}
            return obj
        return _redact_obj(self)


def _apply_overrides(config: NexusConfig, overrides: dict[str, Any]) -> NexusConfig:
    """Apply dotted-key overrides to a frozen config."""
    import dataclasses

    top_updates = {}
    nested_updates = {}
    for key, value in overrides.items():
        if "." in key:
            section, sub_key = key.split(".", 1)
            nested_updates.setdefault(section, {})[sub_key] = value
        else:
            top_updates[key] = value

    for section, updates in nested_updates.items():
        if not hasattr(config, section):
            raise ConfigurationError(f"Unknown config section: {section!r}")
        current = getattr(config, section)
        new_section = dataclasses.replace(current, **updates)
        top_updates[section] = new_section

    return dataclasses.replace(config, **top_updates)


def load_config(
    *,
    env_file: str | Path = ".env",
    environment_override: Environment | None = None,
    overrides: dict[str, Any] | None = None,
) -> NexusConfig:
    """
    Load configuration from environment, .env, defaults, and overrides.

    Precedence:
        1. overrides (explicit kwargs)
        2. real environment variables
        3. .env file
        4. hard-coded defaults
    """
    dotenv_values = _parse_dotenv(Path(env_file))
    _voice_defaults = _default_instance(VoiceConfig)
    _llm_defaults = _default_instance(LLMConfig)
    _memory_defaults = _default_instance(MemoryConfig)
    _security_defaults = _default_instance(SecurityConfig)

    def _get(key: str, default: str) -> str:
        if key in os.environ:
            return os.environ[key]
        return dotenv_values.get(key, default)

    def _get_bool(key: str, default: bool) -> bool:
        raw = _get(key, str(default))
        return raw.lower() in ("1", "true", "yes", "on")

    def _get_int(key: str, default: int) -> int:
        raw = _get(key, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigurationError(f"Env var {key!r} must be int, got {raw!r}") from exc

    def _get_float(key: str, default: float) -> float:
        raw = _get(key, str(default))
        try:
            return float(raw)
        except ValueError as exc:
            raise ConfigurationError(f"Env var {key!r} must be float, got {raw!r}") from exc

    # Environment
    env_name = (
        environment_override.value
        if environment_override is not None
        else _get("NEXUS_ENVIRONMENT", Environment.DEVELOPMENT.value)
    )
    try:
        environment = Environment(env_name)
    except ValueError as exc:
        valid = ", ".join(e.value for e in Environment)
        raise ConfigurationError(f"Invalid NEXUS_ENVIRONMENT={env_name!r}. Must be one of: {valid}") from exc

    voice = VoiceConfig(
        wake_word=_get("NEXUS_WAKE_WORD", _voice_defaults.wake_word),
        wake_word_sensitivity=_get_float("NEXUS_WAKE_WORD_SENSITIVITY", _voice_defaults.wake_word_sensitivity),
        stt_model=_get("NEXUS_STT_MODEL", _voice_defaults.stt_model),
        stt_streaming=_get_bool("NEXUS_STT_STREAMING", _voice_defaults.stt_streaming),
        tts_provider=_get("NEXUS_TTS_PROVIDER", _voice_defaults.tts_provider),
        tts_voice_id=_get("NEXUS_TTS_VOICE_ID", _voice_defaults.tts_voice_id),
        sample_rate_hz=_get_int("NEXUS_SAMPLE_RATE_HZ", _voice_defaults.sample_rate_hz),
        vad_aggressiveness=_get_float("NEXUS_VAD_AGGRESSIVENESS", _voice_defaults.vad_aggressiveness),
    )

    llm = LLMConfig(
        provider=_get("NEXUS_LLM_PROVIDER", _llm_defaults.provider),
        model_name=_get("NEXUS_LLM_MODEL", _llm_defaults.model_name),
        api_key=_get("NEXUS_LLM_API_KEY", _llm_defaults.api_key),
        base_url=_get("NEXUS_LLM_BASE_URL", _llm_defaults.base_url),
        max_tokens=_get_int("NEXUS_LLM_MAX_TOKENS", _llm_defaults.max_tokens),
        temperature=_get_float("NEXUS_LLM_TEMPERATURE", _llm_defaults.temperature),
        request_timeout_s=_get_float("NEXUS_LLM_TIMEOUT_S", _llm_defaults.request_timeout_s),
    )

    memory = MemoryConfig(
        vector_db_provider=_get("NEXUS_VECTOR_DB_PROVIDER", _memory_defaults.vector_db_provider),
        vector_db_url=_get("NEXUS_VECTOR_DB_URL", _memory_defaults.vector_db_url),
        postgres_dsn=_get("NEXUS_POSTGRES_DSN", _memory_defaults.postgres_dsn),
        knowledge_graph_enabled=_get_bool("NEXUS_KNOWLEDGE_GRAPH_ENABLED", _memory_defaults.knowledge_graph_enabled),
        neo4j_uri=_get("NEXUS_NEO4J_URI", _memory_defaults.neo4j_uri),
        short_term_max_turns=_get_int("NEXUS_SHORT_TERM_MAX_TURNS", _memory_defaults.short_term_max_turns),
        summary_every_n_turns=_get_int("NEXUS_SUMMARY_EVERY_N_TURNS", _memory_defaults.summary_every_n_turns),
    )

    security = SecurityConfig(
        blocked_package_substrings=tuple(
            s.strip() for s in _get("NEXUS_BLOCKED_PACKAGE_SUBSTRINGS", ",".join(_security_defaults.blocked_package_substrings)).split(",") if s.strip()
        ),
        confirm_required_actions=tuple(
            s.strip() for s in _get("NEXUS_CONFIRM_REQUIRED_ACTIONS", ",".join(_security_defaults.confirm_required_actions)).split(",") if s.strip()
        ),
        audit_log_path=_get("NEXUS_AUDIT_LOG_PATH", _security_defaults.audit_log_path),
        encrypt_memory_at_rest=_get_bool("NEXUS_ENCRYPT_MEMORY_AT_REST", _security_defaults.encrypt_memory_at_rest),
        max_actions_per_minute=_get_int("NEXUS_MAX_ACTIONS_PER_MINUTE", _security_defaults.max_actions_per_minute),
    )

    config = NexusConfig(
        environment=environment,
        log_level=_get("NEXUS_LOG_LEVEL", "INFO"),
        log_dir=_get("NEXUS_LOG_DIR", "./data/logs"),
        data_dir=_get("NEXUS_DATA_DIR", "./data"),
        supported_languages=tuple(lang.strip() for lang in _get("NEXUS_SUPPORTED_LANGUAGES", "en,ne").split(",") if lang.strip()),
        voice=voice,
        llm=llm,
        memory=memory,
        security=security,
    )

    if overrides:
        config = _apply_overrides(config, overrides)

    # Validate constraints
    if not (0.0 <= config.voice.wake_word_sensitivity <= 1.0):
        raise ConfigurationError("NEXUS_WAKE_WORD_SENSITIVITY must be between 0.0 and 1.0")
    if not (0.0 <= config.voice.vad_aggressiveness <= 1.0):
        raise ConfigurationError("NEXUS_VAD_AGGRESSIVENESS must be between 0.0 and 1.0")
    if config.security.max_actions_per_minute <= 0:
        raise ConfigurationError("NEXUS_MAX_ACTIONS_PER_MINUTE must be positive")
    if config.llm.max_tokens <= 0:
        raise ConfigurationError("NEXUS_LLM_MAX_TOKENS must be positive")

    return config