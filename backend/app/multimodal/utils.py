"""
Utility functions for the multimodal RAG module.
Inspired by RAG-Anything's utils.
"""

import base64
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """Encode an image file to base64 string."""
    try:
        path = Path(image_path)
        if not path.exists():
            print(f"Image file not found: {image_path}")
            return None
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None


def validate_image_file(image_path: str, max_size_mb: int = 50) -> bool:
    """Validate that a file is a valid image."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
    try:
        path = Path(image_path)
        if not path.exists():
            return False
        if path.suffix.lower() not in valid_extensions:
            return False
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            return False
        return True
    except Exception:
        return False


def get_image_mime_type(image_path: str) -> str:
    """Get the MIME type for an image file."""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mime_map.get(ext, "image/png")


def generate_content_hash(content: str) -> str:
    """Generate MD5 hash for content."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def generate_cache_key(file_path: str, config_str: str = "") -> str:
    """Generate a cache key for a parsed document."""
    path = Path(file_path)
    mtime = path.stat().st_mtime if path.exists() else 0
    raw = f"{file_path}:{mtime}:{config_str}"
    return hashlib.md5(raw.encode()).hexdigest()


def separate_content(content_list: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Separate a content list into text content and multimodal items.
    Inspired by RAG-Anything's separate_content utility.

    Args:
        content_list: List of content blocks from document parser.
            Each block has a 'type' field: 'text', 'image', 'table', 'equation'

    Returns:
        Tuple of (text_content_string, list_of_multimodal_items)
    """
    text_parts = []
    multimodal_items = []

    for item in content_list:
        content_type = item.get("type", "text")
        if content_type == "text":
            text = item.get("text", "").strip()
            if text:
                text_parts.append(text)
        else:
            multimodal_items.append(item)

    return "\n\n".join(text_parts), multimodal_items


def extract_context_for_item(
    content_list: List[Dict],
    item_index: int,
    window: int = 2,
    max_tokens: int = 2000
) -> str:
    """
    Extract surrounding text context for a multimodal item.
    Inspired by RAG-Anything's ContextExtractor.

    Args:
        content_list: Full content list from parser
        item_index: Index of the multimodal item
        window: Number of items before/after to include
        max_tokens: Maximum characters (approx) in context

    Returns:
        Context string
    """
    context_parts = []
    start = max(0, item_index - window)
    end = min(len(content_list), item_index + window + 1)

    for i in range(start, end):
        if i == item_index:
            continue
        item = content_list[i]
        if item.get("type") == "text":
            text = item.get("text", "").strip()
            if text:
                context_parts.append(text)

    context = "\n".join(context_parts)
    # Truncate to max_tokens (rough character-based)
    if len(context) > max_tokens * 4:
        context = context[: max_tokens * 4]
        # Try to cut at sentence boundary
        last_period = context.rfind(". ")
        if last_period > len(context) * 0.5:
            context = context[: last_period + 1]

    return context


def robust_json_parse(text: str) -> Optional[Dict]:
    """
    Multi-strategy JSON parsing.
    Inspired by RAG-Anything's _robust_json_parse.
    """
    if not text:
        return None

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract JSON block from text
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Clean up common issues
    cleaned = text
    # Remove markdown code blocks
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*", "", cleaned)
    # Fix single quotes
    cleaned = cleaned.replace("'", '"')

    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: Regex field extraction
    try:
        result = {}
        desc_match = re.search(
            r'"detailed_description"\s*:\s*"([^"]*(?:(?:\\")?[^"]*)*)"', text
        )
        if desc_match:
            result["detailed_description"] = desc_match.group(1).replace('\\"', '"')

        name_match = re.search(r'"entity_name"\s*:\s*"([^"]*)"', text)
        if name_match:
            result["entity_info"] = {
                "entity_name": name_match.group(1),
                "entity_type": "unknown",
                "summary": result.get("detailed_description", "")[:100],
            }

        type_match = re.search(r'"entity_type"\s*:\s*"([^"]*)"', text)
        if type_match and "entity_info" in result:
            result["entity_info"]["entity_type"] = type_match.group(1)

        summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', text)
        if summary_match and "entity_info" in result:
            result["entity_info"]["summary"] = summary_match.group(1)

        if result:
            return result
    except Exception:
        pass

    return None


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    if not text or not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Try to break at sentence boundary
            for delim in [". ", ".\n", "! ", "?\n", "\n\n"]:
                last_delim = text[start:end].rfind(delim)
                if last_delim != -1:
                    end = start + last_delim + len(delim)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += (chunk_size - overlap)

    return chunks


def get_processor_for_type(content_type: str) -> str:
    """Map content type to processor name."""
    type_map = {
        "image": "image",
        "img": "image",
        "figure": "image",
        "table": "table",
        "tab": "table",
        "equation": "equation",
        "formula": "equation",
        "math": "equation",
    }
    return type_map.get(content_type.lower(), "generic")
