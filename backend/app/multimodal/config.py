"""
Configuration for the Multimodal RAG module.
Inspired by RAG-Anything's RAGAnythingConfig.
"""

import os
from dataclasses import dataclass, field
from typing import List


def get_env(key: str, default, cast=str):
    """Get environment variable with type casting."""
    val = os.getenv(key, None)
    if val is None:
        return default
    if cast == bool:
        return val.lower() in ("true", "1", "yes")
    return cast(val)


@dataclass
class MultimodalConfig:
    """Configuration for multimodal RAG processing."""

    # ---- Directory ----
    working_dir: str = field(default_factory=lambda: get_env("VECTOR_STORE_PATH", "./data/vector_store"))
    documents_dir: str = field(default_factory=lambda: get_env("DOCUMENTS_PATH", "./data/documents"))
    parser_output_dir: str = field(default_factory=lambda: get_env("PARSER_OUTPUT_DIR", "./data/parser_output"))

    # ---- LLM / Ollama ----
    ollama_host: str = field(default_factory=lambda: get_env("OLLAMA_HOST", "http://ollama:11434"))
    llm_model: str = field(default_factory=lambda: get_env("OLLAMA_LLM_MODEL", "llama3.1"))
    vision_model: str = field(default_factory=lambda: get_env("OLLAMA_VISION_MODEL", "llava"))
    temperature: float = field(default_factory=lambda: get_env("LLM_TEMPERATURE", 0.1, float))

    # ---- Embedding ----
    embedding_provider: str = field(default_factory=lambda: get_env("EMBEDDING_PROVIDER", "sentence-transformers"))
    embedding_model: str = field(default_factory=lambda: get_env("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

    # ---- Multimodal Processing Toggles ----
    enable_image_processing: bool = field(default_factory=lambda: get_env("ENABLE_IMAGE_PROCESSING", True, bool))
    enable_table_processing: bool = field(default_factory=lambda: get_env("ENABLE_TABLE_PROCESSING", True, bool))
    enable_equation_processing: bool = field(default_factory=lambda: get_env("ENABLE_EQUATION_PROCESSING", True, bool))

    # ---- Document Parsing ----
    chunk_size: int = field(default_factory=lambda: get_env("CHUNK_SIZE", 1000, int))
    chunk_overlap: int = field(default_factory=lambda: get_env("CHUNK_OVERLAP", 200, int))
    max_file_size_mb: int = field(default_factory=lambda: get_env("MAX_FILE_SIZE_MB", 100, int))
    supported_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".docx", ".doc", ".txt", ".md",
        ".xlsx", ".xls", ".pptx", ".ppt",
        ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp",
        ".html", ".htm", ".csv"
    ])

    # ---- Context Extraction ----
    context_window: int = field(default_factory=lambda: get_env("CONTEXT_WINDOW", 2, int))
    max_context_tokens: int = field(default_factory=lambda: get_env("MAX_CONTEXT_TOKENS", 2000, int))

    # ---- Batch Processing ----
    max_concurrent_files: int = field(default_factory=lambda: get_env("MAX_CONCURRENT_FILES", 3, int))

    # ---- Knowledge Graph ----
    kg_persist_path: str = field(default_factory=lambda: get_env("KG_PERSIST_PATH", "./data/vector_store"))
    entity_types: List[str] = field(default_factory=lambda: [
        "PERSON", "ORGANIZATION", "PROJECT", "TECHNOLOGY",
        "PRODUCT", "LOCATION", "CONCEPT", "IMAGE", "TABLE", "EQUATION"
    ])

    def __post_init__(self):
        """Ensure directories exist."""
        import pathlib
        for d in [self.working_dir, self.documents_dir, self.parser_output_dir]:
            pathlib.Path(d).mkdir(parents=True, exist_ok=True)
