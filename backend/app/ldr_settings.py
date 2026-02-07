"""
Settings adapter for Local Deep Research (LDR) integration.
Builds settings_snapshot dicts from environment variables and database settings.
"""
import os
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.models import ResearchSetting


# Default LDR settings
DEFAULT_SETTINGS = {
    "llm.provider": "ollama",
    "llm.model": "llama3.1",
    "llm.temperature": 0.7,
    "llm.ollama.url": "http://ollama:11434",
    "llm.context_length": 4096,
    "search.tool": "searxng",
    "search.iterations": 3,
    "search.questions_per_iteration": 3,
    "search.max_results": 50,
    "search.snippets_only": True,
    "search.region": "",
    "search.time_period": "",
    "search.safe_search": False,
    "search.searxng.url": "http://searxng:8080",
    "search.searxng.language": "en",
    "report.searches_per_section": 2,
    "embedding.provider": "sentence-transformers",
    "embedding.model": "all-MiniLM-L6-v2",
}


def build_settings_snapshot(db: Optional[Session] = None, overrides: Optional[Dict] = None) -> Dict:
    """
    Build a settings snapshot by merging defaults, env vars, DB settings, and overrides.
    Priority: overrides > DB settings > env vars > defaults
    """
    snapshot = dict(DEFAULT_SETTINGS)

    # Override from environment variables
    env_mappings = {
        "OLLAMA_HOST": "llm.ollama.url",
        "OLLAMA_LLM_MODEL": "llm.model",
        "OLLAMA_CONTEXT_LENGTH": "llm.context_length",
        "SEARXNG_URL": "search.searxng.url",
        "LDR_SEARCH_TOOL": "search.tool",
        "LDR_SEARCH_ITERATIONS": "search.iterations",
        "LDR_QUESTIONS_PER_ITERATION": "search.questions_per_iteration",
        "LDR_MAX_RESULTS": "search.max_results",
        "LDR_SEARCHES_PER_SECTION": "report.searches_per_section",
        "EMBEDDING_PROVIDER": "embedding.provider",
        "EMBEDDING_MODEL": "embedding.model",
    }

    for env_key, setting_key in env_mappings.items():
        env_val = os.getenv(env_key)
        if env_val is not None:
            # Convert to appropriate type
            if setting_key in ("search.iterations", "search.questions_per_iteration",
                               "search.max_results", "report.searches_per_section",
                               "llm.context_length"):
                try:
                    snapshot[setting_key] = int(env_val)
                except ValueError:
                    pass
            elif setting_key == "llm.temperature":
                try:
                    snapshot[setting_key] = float(env_val)
                except ValueError:
                    pass
            else:
                snapshot[setting_key] = env_val

    # Override from database settings (global settings where user_id is NULL)
    if db is not None:
        try:
            db_settings = db.query(ResearchSetting).filter(
                ResearchSetting.user_id.is_(None)
            ).all()
            for setting in db_settings:
                snapshot[setting.key] = _cast_value(setting.key, setting.value)
        except Exception as e:
            print(f"Warning: Could not load DB settings: {e}")

    # Apply overrides
    if overrides:
        for key, value in overrides.items():
            snapshot[key] = value

    return snapshot


def get_all_settings(db: Session) -> Dict:
    """Get all current settings as a flat dict for the API."""
    snapshot = build_settings_snapshot(db)
    return snapshot


def update_settings(db: Session, settings: Dict) -> Dict:
    """Update settings in the database."""
    for key, value in settings.items():
        if key not in DEFAULT_SETTINGS:
            continue

        existing = db.query(ResearchSetting).filter(
            ResearchSetting.user_id.is_(None),
            ResearchSetting.key == key
        ).first()

        str_value = str(value)

        if existing:
            existing.value = str_value
        else:
            new_setting = ResearchSetting(
                user_id=None,
                key=key,
                value=str_value
            )
            db.add(new_setting)

    db.commit()
    return get_all_settings(db)


def _cast_value(key: str, value: str):
    """Cast a string value to the appropriate type based on the key."""
    int_keys = {"search.iterations", "search.questions_per_iteration",
                "search.max_results", "report.searches_per_section",
                "llm.context_length"}
    float_keys = {"llm.temperature"}
    bool_keys = {"search.snippets_only", "search.safe_search"}

    if key in int_keys:
        try:
            return int(value)
        except ValueError:
            return value
    elif key in float_keys:
        try:
            return float(value)
        except ValueError:
            return value
    elif key in bool_keys:
        return value.lower() in ("true", "1", "yes")
    return value
