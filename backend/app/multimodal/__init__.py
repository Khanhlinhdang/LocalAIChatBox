"""
Multimodal RAG Module for LocalAIChatBox
Inspired by RAG-Anything - provides multimodal document processing,
knowledge graph construction, and intelligent retrieval.
"""

from .config import MultimodalConfig
from .document_parser import DocumentParserService
from .modal_processors import (
    ImageProcessor,
    TableProcessor,
    EquationProcessor,
    GenericProcessor,
)
from .query_engine import QueryEngine
from .prompts import PROMPTS

__all__ = [
    "MultimodalConfig",
    "DocumentParserService",
    "ImageProcessor",
    "TableProcessor",
    "EquationProcessor",
    "GenericProcessor",
    "QueryEngine",
    "PROMPTS",
]
