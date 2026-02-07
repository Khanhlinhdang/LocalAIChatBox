"""
Query engine with multimodal support.
Inspired by RAG-Anything's QueryMixin.

Supports:
- Text-only queries
- Multimodal-enhanced queries
- VLM-enhanced queries (vision model for image understanding)
- Hybrid search modes (vector + knowledge graph)
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .prompts import PROMPTS
from .utils import encode_image_to_base64, get_image_mime_type


class QueryEngine:
    """
    Advanced query engine with multimodal support.
    Works with EnhancedRAGEngine for searching and LLM for answering.
    """

    def __init__(self, rag_engine):
        """
        Args:
            rag_engine: EnhancedRAGEngine instance
        """
        self.rag_engine = rag_engine

    def query(
        self,
        question: str,
        mode: str = "hybrid",
        k: int = 5,
        use_knowledge_graph: bool = True,
        include_multimodal: bool = True,
    ) -> Dict:
        """
        Main query method with multiple modes.

        Modes:
        - "naive": Simple vector search without KG
        - "local": Vector search with local KG context
        - "global": Vector search with full KG context
        - "hybrid": Combined vector + KG search (default)

        Returns:
            {
                "answer": str,
                "sources": List[str],
                "num_sources": int,
                "entities_found": List[Dict],
                "graph_connections": int,
                "multimodal_results": int,
                "search_mode": str,
            }
        """
        # Get knowledge graph context
        graph_context = ""
        entities_found = []
        graph_connections = 0

        if use_knowledge_graph and mode != "naive":
            try:
                from app.knowledge_graph import get_kg_engine
                kg_engine = get_kg_engine()
                graph_context = kg_engine.get_graph_context(question)
                entities = kg_engine.find_entities(question)
                entities_found = entities[:5]
                for e in entities_found[:3]:
                    sub = kg_engine.get_entity_subgraph(e["name"], max_hops=2)
                    graph_connections += len(sub.get("edges", []))
            except Exception as e:
                print(f"KG query error (non-fatal): {e}")

        # Search and generate answer
        result = self.rag_engine.query_with_context(
            question=question,
            k=k,
            graph_context=graph_context,
            include_multimodal=include_multimodal,
        )

        # Count multimodal results
        search_results = self.rag_engine.search(question, k=k, include_multimodal=include_multimodal)
        mm_count = sum(1 for r in search_results if r.get("source") == "multimodal")

        result["entities_found"] = entities_found
        result["graph_connections"] = graph_connections
        result["multimodal_results"] = mm_count
        result["search_mode"] = mode

        return result

    def query_with_multimodal_content(
        self,
        question: str,
        multimodal_content: List[Dict],
        mode: str = "hybrid",
        k: int = 5,
    ) -> Dict:
        """
        Query with additional multimodal content provided by the user.
        Inspired by RAG-Anything's aquery_with_multimodal.

        The multimodal content is processed and used to enhance the query.

        Args:
            question: User's question text
            multimodal_content: List of multimodal items to include:
                [
                    {"type": "image", "img_path": "/path/to/img.png"},
                    {"type": "table", "table_body": "markdown table"},
                    {"type": "equation", "text": "E=mc^2"},
                ]
            mode: Search mode
            k: Number of results

        Returns:
            Enhanced query result
        """
        # Process multimodal content to get descriptions
        enhanced_parts = []
        manager = self.rag_engine._get_processor_manager()

        for item in multimodal_content:
            content_type = item.get("type", "unknown")
            processor = manager.get_processor(content_type)

            try:
                desc_result = processor.generate_description(item)
                description = desc_result.get("description", "")
                if description:
                    enhanced_parts.append(
                        f"[{content_type.upper()} CONTENT]: {description}"
                    )
            except Exception as e:
                print(f"Error processing multimodal query content: {e}")

        # Enhance the question with multimodal descriptions
        if enhanced_parts:
            enhanced_query = (
                question
                + "\n\nAdditional multimodal content:\n"
                + "\n".join(enhanced_parts)
                + PROMPTS["QUERY_ENHANCEMENT_SUFFIX"]
            )
        else:
            enhanced_query = question

        return self.query(
            question=enhanced_query,
            mode=mode,
            k=k,
            include_multimodal=True,
        )

    def query_vlm_enhanced(
        self,
        question: str,
        image_paths: List[str] = None,
        k: int = 5,
    ) -> Dict:
        """
        VLM-enhanced query that can process images directly.
        Inspired by RAG-Anything's aquery_vlm_enhanced.

        Args:
            question: User's question
            image_paths: Optional list of image paths to analyze
            k: Number of search results

        Returns:
            Query result with VLM-enhanced answer
        """
        # First do normal retrieval
        search_results = self.rag_engine.search(question, k=k, include_multimodal=True)

        # Build context from search results
        context_parts = []
        sources = []
        for r in search_results:
            context_parts.append(r["text"])
            filename = r.get("metadata", {}).get("filename", "Unknown")
            if filename not in sources:
                sources.append(filename)

        context = "\n\n---\n\n".join(context_parts)

        # Process user-provided images with vision model
        image_descriptions = []
        if image_paths:
            llm_client = self.rag_engine._get_llm_client()
            for img_path in image_paths:
                img_b64 = encode_image_to_base64(img_path)
                if img_b64:
                    desc = llm_client.generate_vision(
                        PROMPTS["IMAGE_ANALYSIS_SYSTEM"],
                        PROMPTS["QUERY_IMAGE_DESCRIPTION"],
                        img_b64,
                        get_image_mime_type(img_path),
                    )
                    if desc:
                        image_descriptions.append(f"[Image: {Path(img_path).name}]: {desc}")

        # Build enhanced prompt
        image_context = "\n".join(image_descriptions) if image_descriptions else ""

        full_prompt = PROMPTS["RAG_QUERY_WITH_CONTEXT"].format(
            context=context,
            graph_context="",
            multimodal_context=f"\n=== IMAGE ANALYSIS ===\n{image_context}" if image_context else "",
            question=question,
        )

        answer = self.rag_engine._generate_answer(PROMPTS["RAG_SYSTEM"], full_prompt)

        return {
            "answer": answer,
            "sources": sources,
            "num_sources": len(sources),
            "images_analyzed": len(image_descriptions),
        }

    def get_search_results_only(
        self,
        question: str,
        k: int = 10,
        include_multimodal: bool = True,
    ) -> Dict:
        """
        Get raw search results without LLM answer generation.
        Useful for debugging or showing search results directly.
        """
        results = self.rag_engine.search(question, k=k, include_multimodal=include_multimodal)

        return {
            "query": question,
            "total_results": len(results),
            "results": [
                {
                    "text": r["text"][:500],
                    "metadata": r.get("metadata", {}),
                    "distance": r.get("distance", 0),
                    "source_type": r.get("source", "text"),
                }
                for r in results
            ],
        }
