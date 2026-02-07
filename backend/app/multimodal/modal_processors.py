"""
Multimodal content processors for images, tables, equations, and generic content.
Inspired by RAG-Anything's modal processors architecture.

Each processor:
1. Generates descriptions using LLM/VLM
2. Formats content into structured chunks
3. Extracts entities for the knowledge graph
"""

import json
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .prompts import PROMPTS
from .utils import encode_image_to_base64, get_image_mime_type, robust_json_parse, validate_image_file


class LLMClient:
    """Unified LLM client for multimodal processors using Ollama."""

    def __init__(self, ollama_host: str, llm_model: str, vision_model: str = "llava", temperature: float = 0.1):
        self.ollama_host = ollama_host
        self.llm_model = llm_model
        self.vision_model = vision_model
        self.temperature = temperature

    def _get_chat_client(self):
        """Get LangChain chat client."""
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=self.ollama_host,
                model=self.llm_model,
                temperature=self.temperature,
            )
        except ImportError:
            return None

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text response from LLM."""
        try:
            llm = self._get_chat_client()
            if llm:
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                response = llm.invoke(messages)
                return response.content
            else:
                # Fallback to raw ollama
                import requests
                resp = requests.post(
                    f"{self.ollama_host}/api/chat",
                    json={
                        "model": self.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {"temperature": self.temperature},
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]
        except Exception as e:
            print(f"LLM generation error: {e}")
            return ""

    def generate_vision(self, system_prompt: str, user_prompt: str, image_base64: str, mime_type: str = "image/png") -> str:
        """Generate response from vision model with image input."""
        try:
            import requests
            resp = requests.post(
                f"{self.ollama_host}/api/chat",
                json={
                    "model": self.vision_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": user_prompt,
                            "images": [image_base64],
                        },
                    ],
                    "stream": False,
                    "options": {"temperature": self.temperature},
                },
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            print(f"Vision model error: {e}")
            return ""


class BaseModalProcessor:
    """Base class for all modal processors."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.content_source = None

    def set_content_source(self, content_list: List[Dict]):
        """Set content source for context extraction."""
        self.content_source = content_list

    def _get_context(self, item: Dict, index: int = -1) -> str:
        """Get surrounding context for a multimodal item."""
        if not self.content_source:
            return ""
        from .utils import extract_context_for_item
        if index >= 0:
            return extract_context_for_item(self.content_source, index)
        # Find item in content source
        for i, src_item in enumerate(self.content_source):
            if src_item is item or src_item.get("img_path") == item.get("img_path"):
                return extract_context_for_item(self.content_source, i)
        return ""

    def generate_description(self, item: Dict, index: int = -1) -> Dict:
        """Generate description for a multimodal item. Override in subclasses."""
        raise NotImplementedError

    def format_chunk(self, item: Dict, description: str) -> str:
        """Format the item as a chunk for RAG storage. Override in subclasses."""
        raise NotImplementedError

    def extract_entities(self, item: Dict, description: str, source_doc: str = "") -> Tuple[List[Dict], List[Dict]]:
        """Extract entities and relations from multimodal content description."""
        prompt = PROMPTS["MULTIMODAL_ENTITY_EXTRACTION"].format(
            content_type=item.get("type", "unknown"),
            description=description[:2000],
            source_doc=source_doc,
        )
        try:
            result_text = self.llm_client.generate_text(
                "You are an entity extraction expert. Return ONLY valid JSON.",
                prompt,
            )
            parsed = robust_json_parse(result_text)
            if parsed:
                return parsed.get("entities", []), parsed.get("relations", [])
        except Exception as e:
            print(f"Entity extraction error: {e}")
        return [], []


class ImageProcessor(BaseModalProcessor):
    """Processor for image content."""

    def generate_description(self, item: Dict, index: int = -1) -> Dict:
        """Generate description for an image using vision model."""
        img_path = item.get("img_path", "")
        captions = item.get("image_caption", [])
        footnotes = item.get("image_footnote", [])

        # Generate entity name from filename
        entity_name = Path(img_path).stem if img_path else "unnamed_image"
        caption_str = ", ".join(captions) if captions else "No caption"
        footnote_str = ", ".join(footnotes) if footnotes else "None"

        context = self._get_context(item, index)

        # Try vision model first
        if img_path and validate_image_file(img_path):
            img_b64 = encode_image_to_base64(img_path)
            if img_b64:
                if context:
                    prompt = PROMPTS["vision_prompt_with_context"].format(
                        entity_name=entity_name,
                        image_path=img_path,
                        captions=caption_str,
                        footnotes=footnote_str,
                        context=context,
                    )
                else:
                    prompt = PROMPTS["vision_prompt"].format(
                        entity_name=entity_name,
                        image_path=img_path,
                        captions=caption_str,
                        footnotes=footnote_str,
                    )

                response = self.llm_client.generate_vision(
                    PROMPTS["IMAGE_ANALYSIS_SYSTEM"],
                    prompt,
                    img_b64,
                    get_image_mime_type(img_path),
                )

                parsed = robust_json_parse(response)
                if parsed:
                    return {
                        "description": parsed.get("detailed_description", response),
                        "entity_info": parsed.get("entity_info", {
                            "entity_name": entity_name,
                            "entity_type": "image",
                            "summary": caption_str,
                        }),
                        "raw_response": response,
                    }

                return {
                    "description": response or f"Image: {caption_str}",
                    "entity_info": {
                        "entity_name": entity_name,
                        "entity_type": "image",
                        "summary": caption_str,
                    },
                    "raw_response": response,
                }

        # Fallback: text-only description
        fallback = f"Image at {img_path}. Caption: {caption_str}. Footnotes: {footnote_str}"
        return {
            "description": fallback,
            "entity_info": {
                "entity_name": entity_name,
                "entity_type": "image",
                "summary": caption_str,
            },
            "raw_response": "",
        }

    def format_chunk(self, item: Dict, description: str) -> str:
        """Format image content as a chunk."""
        return PROMPTS["image_chunk"].format(
            image_path=item.get("img_path", ""),
            captions=", ".join(item.get("image_caption", [])) or "None",
            footnotes=", ".join(item.get("image_footnote", [])) or "None",
            enhanced_caption=description,
        )


class TableProcessor(BaseModalProcessor):
    """Processor for table content."""

    def generate_description(self, item: Dict, index: int = -1) -> Dict:
        """Generate description for a table."""
        table_body = item.get("table_body", "")
        table_caption = item.get("table_caption", [])
        table_footnote = item.get("table_footnote", [])

        entity_name = f"table_{item.get('page_idx', 0)}"
        caption_str = ", ".join(table_caption) if table_caption else "No caption"
        footnote_str = ", ".join(table_footnote) if table_footnote else "None"

        context = self._get_context(item, index)

        if context:
            prompt = PROMPTS["table_prompt_with_context"].format(
                entity_name=entity_name,
                table_caption=caption_str,
                table_body=table_body[:3000],
                table_footnote=footnote_str,
                context=context,
            )
        else:
            prompt = PROMPTS["table_prompt"].format(
                entity_name=entity_name,
                table_caption=caption_str,
                table_body=table_body[:3000],
                table_footnote=footnote_str,
            )

        response = self.llm_client.generate_text(
            PROMPTS["TABLE_ANALYSIS_SYSTEM"],
            prompt,
        )

        parsed = robust_json_parse(response)
        if parsed:
            return {
                "description": parsed.get("detailed_description", response),
                "entity_info": parsed.get("entity_info", {
                    "entity_name": entity_name,
                    "entity_type": "table",
                    "summary": caption_str,
                }),
                "raw_response": response,
            }

        return {
            "description": response or f"Table: {caption_str}. Content: {table_body[:500]}",
            "entity_info": {
                "entity_name": entity_name,
                "entity_type": "table",
                "summary": caption_str,
            },
            "raw_response": response,
        }

    def format_chunk(self, item: Dict, description: str) -> str:
        """Format table content as a chunk."""
        return PROMPTS["table_chunk"].format(
            table_caption=", ".join(item.get("table_caption", [])) or "None",
            table_body=item.get("table_body", "")[:2000],
            table_footnote=", ".join(item.get("table_footnote", [])) or "None",
            enhanced_caption=description,
        )


class EquationProcessor(BaseModalProcessor):
    """Processor for equation content."""

    def generate_description(self, item: Dict, index: int = -1) -> Dict:
        """Generate description for an equation."""
        eq_text = item.get("text", "")
        eq_format = item.get("equation_format", "text")

        entity_name = f"equation_{item.get('page_idx', 0)}"

        context = self._get_context(item, index)

        if context:
            prompt = PROMPTS["equation_prompt_with_context"].format(
                entity_name=entity_name,
                equation_text=eq_text,
                equation_format=eq_format,
                context=context,
            )
        else:
            prompt = PROMPTS["equation_prompt"].format(
                entity_name=entity_name,
                equation_text=eq_text,
                equation_format=eq_format,
            )

        response = self.llm_client.generate_text(
            PROMPTS["EQUATION_ANALYSIS_SYSTEM"],
            prompt,
        )

        parsed = robust_json_parse(response)
        if parsed:
            return {
                "description": parsed.get("detailed_description", response),
                "entity_info": parsed.get("entity_info", {
                    "entity_name": entity_name,
                    "entity_type": "equation",
                    "summary": eq_text[:100],
                }),
                "raw_response": response,
            }

        return {
            "description": response or f"Equation: {eq_text}",
            "entity_info": {
                "entity_name": entity_name,
                "entity_type": "equation",
                "summary": eq_text[:100],
            },
            "raw_response": response,
        }

    def format_chunk(self, item: Dict, description: str) -> str:
        """Format equation content as a chunk."""
        return PROMPTS["equation_chunk"].format(
            equation_text=item.get("text", ""),
            equation_format=item.get("equation_format", "text"),
            enhanced_caption=description,
        )


class GenericProcessor(BaseModalProcessor):
    """Fallback processor for unknown content types."""

    def generate_description(self, item: Dict, index: int = -1) -> Dict:
        """Generate description for generic content."""
        content_type = item.get("type", "unknown")
        content = json.dumps(item, default=str)[:2000]
        entity_name = f"{content_type}_{item.get('page_idx', 0)}"

        prompt = PROMPTS["generic_prompt"].format(
            content_type=content_type,
            entity_name=entity_name,
            content=content,
        )

        response = self.llm_client.generate_text(
            PROMPTS["GENERIC_ANALYSIS_SYSTEM"].format(content_type=content_type),
            prompt,
        )

        parsed = robust_json_parse(response)
        if parsed:
            return {
                "description": parsed.get("detailed_description", response),
                "entity_info": parsed.get("entity_info", {
                    "entity_name": entity_name,
                    "entity_type": content_type,
                    "summary": "",
                }),
                "raw_response": response,
            }

        return {
            "description": response or f"Content ({content_type}): {content[:200]}",
            "entity_info": {
                "entity_name": entity_name,
                "entity_type": content_type,
                "summary": "",
            },
            "raw_response": response,
        }

    def format_chunk(self, item: Dict, description: str) -> str:
        """Format generic content as a chunk."""
        content_type = item.get("type", "unknown")
        return PROMPTS["generic_chunk"].format(
            content_type=content_type.upper(),
            content=json.dumps(item, default=str)[:1000],
            enhanced_caption=description,
        )


class MultimodalProcessorManager:
    """
    Manages all multimodal processors.
    Inspired by RAG-Anything's processor initialization pattern.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.processors = {
            "image": ImageProcessor(llm_client),
            "table": TableProcessor(llm_client),
            "equation": EquationProcessor(llm_client),
            "generic": GenericProcessor(llm_client),
        }

    def get_processor(self, content_type: str) -> BaseModalProcessor:
        """Get the appropriate processor for a content type."""
        from .utils import get_processor_for_type
        proc_key = get_processor_for_type(content_type)
        return self.processors.get(proc_key, self.processors["generic"])

    def set_content_source(self, content_list: List[Dict]):
        """Set content source for context extraction on all processors."""
        for proc in self.processors.values():
            proc.set_content_source(content_list)

    def process_item(self, item: Dict, index: int = -1, source_doc: str = "") -> Dict:
        """
        Process a single multimodal item through the full pipeline.

        Returns:
            {
                "type": "image|table|equation|...",
                "description": str,
                "chunk": str,
                "entity_info": {...},
                "entities": [...],
                "relations": [...],
            }
        """
        content_type = item.get("type", "unknown")
        processor = self.get_processor(content_type)

        # Generate description
        desc_result = processor.generate_description(item, index)
        description = desc_result.get("description", "")
        entity_info = desc_result.get("entity_info", {})

        # Format as chunk
        chunk = processor.format_chunk(item, description)

        # Extract entities
        entities, relations = processor.extract_entities(item, description, source_doc)

        # Add the multimodal entity itself
        if entity_info.get("entity_name"):
            entities.insert(0, {
                "name": entity_info["entity_name"],
                "type": entity_info.get("entity_type", content_type).upper(),
                "summary": entity_info.get("summary", ""),
            })

        return {
            "type": content_type,
            "description": description,
            "chunk": chunk,
            "entity_info": entity_info,
            "entities": entities,
            "relations": relations,
        }

    def process_items_batch(
        self, items: List[Dict], source_doc: str = ""
    ) -> List[Dict]:
        """
        Process multiple multimodal items.
        Inspired by RAG-Anything's batch processing pipeline.
        """
        results = []
        for i, item in enumerate(items):
            try:
                result = self.process_item(item, index=i, source_doc=source_doc)
                results.append(result)
            except Exception as e:
                print(f"Error processing multimodal item {i}: {e}")
                traceback.print_exc()
                results.append({
                    "type": item.get("type", "unknown"),
                    "description": f"Error processing: {e}",
                    "chunk": "",
                    "entity_info": {},
                    "entities": [],
                    "relations": [],
                })
        return results
