"""
Enhanced RAG Engine for LocalAIChatBox.
Integrates multimodal content processing with ChromaDB vector storage
and knowledge graph. Inspired by RAG-Anything's processing pipeline.
"""

import hashlib
import json
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import chromadb
from chromadb.config import Settings


class EnhancedRAGEngine:
    """
    Enhanced RAG engine that supports:
    - Text document processing with chunking
    - Multimodal content (images, tables, equations) processing via LLM
    - Knowledge graph construction with multimodal entities
    - Hybrid search (vector + KG)
    - LLM-powered answer generation with context
    """

    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
        self.vision_model = os.getenv("OLLAMA_VISION_MODEL", "llava")
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.vector_store_path = Path(os.getenv("VECTOR_STORE_PATH", "./data/vector_store"))
        self.documents_path = Path(os.getenv("DOCUMENTS_PATH", "./data/documents"))
        self.parser_output_dir = Path(os.getenv("PARSER_OUTPUT_DIR", "./data/parser_output"))

        self._st_model = None
        self._processor_manager = None

        # Create directories
        for d in [self.vector_store_path, self.documents_path, self.parser_output_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.vector_store_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Main documents collection
        try:
            self.collection = self.client.get_collection(name="documents")
            print(f"Loaded existing collection with {self.collection.count()} documents")
        except Exception:
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            print("Created new ChromaDB collection")

        # Multimodal chunks collection
        try:
            self.multimodal_collection = self.client.get_collection(name="multimodal_chunks")
            print(f"Loaded multimodal collection with {self.multimodal_collection.count()} chunks")
        except Exception:
            self.multimodal_collection = self.client.create_collection(
                name="multimodal_chunks",
                metadata={"hnsw:space": "cosine"},
            )
            print("Created new multimodal ChromaDB collection")

    # ================================================================
    # Embedding
    # ================================================================

    def _get_st_model(self):
        """Lazy-load sentence-transformers model."""
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.embedding_model_name)
        return self._st_model

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        if self.embedding_provider == "sentence-transformers":
            return self._embed_with_sentence_transformers(texts)
        else:
            return self._embed_with_ollama(texts)

    def _embed_with_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        model = self._get_st_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.tolist()

    def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
        import requests
        all_embeddings = []
        for text in texts:
            try:
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={"model": self.embedding_model_name, "prompt": text},
                    timeout=30,
                )
                response.raise_for_status()
                all_embeddings.append(response.json()["embedding"])
            except Exception as e:
                print(f"Ollama embedding error: {e}")
                all_embeddings.append([0.0] * 384)
        return all_embeddings

    # ================================================================
    # LLM Client
    # ================================================================

    def _get_llm_client(self):
        """Get or create LLM client for multimodal processing."""
        from .multimodal.modal_processors import LLMClient
        return LLMClient(
            ollama_host=self.ollama_host,
            llm_model=self.llm_model,
            vision_model=self.vision_model,
        )

    def _get_processor_manager(self):
        """Get or create multimodal processor manager."""
        if self._processor_manager is None:
            from .multimodal.modal_processors import MultimodalProcessorManager
            self._processor_manager = MultimodalProcessorManager(self._get_llm_client())
        return self._processor_manager

    # ================================================================
    # Document Processing - Full Pipeline
    # ================================================================

    def process_document_complete(
        self,
        file_path: str,
        doc_id: str,
        filename: str,
        user_id: int = None,
        username: str = "",
        enable_multimodal: bool = True,
    ) -> Dict:
        """
        Complete document processing pipeline inspired by RAG-Anything.

        Steps:
        1. Parse document → content_list with text + multimodal items
        2. Separate text and multimodal content
        3. Chunk and store text in ChromaDB
        4. Process multimodal items (generate descriptions, extract entities)
        5. Store multimodal chunks in ChromaDB
        6. Update knowledge graph with all entities/relations

        Returns:
            Processing result with stats
        """
        from .multimodal.document_parser import DocumentParserService
        from .multimodal.utils import separate_content

        result = {
            "status": "success",
            "text_chunks": 0,
            "multimodal_items": 0,
            "entities_added": 0,
            "relations_added": 0,
            "content_types": {},
        }

        try:
            # Step 1: Parse document
            parser = DocumentParserService(output_dir=str(self.parser_output_dir))
            parsed = parser.parse_document(file_path)
            content_list = parsed["content_list"]
            result["content_types"] = parsed["multimodal_count"]

            # Step 2: Separate text and multimodal
            text_content, multimodal_items = separate_content(content_list)
            text_chunks = parsed["chunks"]

            # Step 3: Store text chunks in ChromaDB
            if text_chunks:
                metadatas = [
                    {
                        "filename": filename,
                        "uploaded_by": username,
                        "user_id": user_id or 0,
                        "chunk_id": i,
                        "content_type": "text",
                        "doc_id": str(doc_id),
                    }
                    for i in range(len(text_chunks))
                ]
                self.add_documents(text_chunks, metadatas, doc_id=str(doc_id))
                result["text_chunks"] = len(text_chunks)

            # Step 4 & 5: Process multimodal items
            if enable_multimodal and multimodal_items:
                mm_result = self._process_multimodal_pipeline(
                    content_list, multimodal_items, doc_id, filename, username, user_id
                )
                result["multimodal_items"] = mm_result.get("items_processed", 0)
                result["entities_added"] += mm_result.get("entities_added", 0)
                result["relations_added"] += mm_result.get("relations_added", 0)

            # Step 6: Extract text entities for knowledge graph
            try:
                from .knowledge_graph import get_kg_engine
                kg_engine = get_kg_engine()
                kg_result = kg_engine.add_document_to_graph(
                    doc_id=str(doc_id),
                    filename=filename,
                    chunks=text_chunks[:20],  # Limit chunks for KG extraction
                )
                result["entities_added"] += kg_result.get("entities_added", 0)
                result["relations_added"] += kg_result.get("relations_added", 0)
            except Exception as e:
                print(f"KG text extraction error (non-fatal): {e}")

        except Exception as e:
            print(f"Document processing error: {e}")
            traceback.print_exc()
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _process_multimodal_pipeline(
        self,
        content_list: List[Dict],
        multimodal_items: List[Dict],
        doc_id: str,
        filename: str,
        username: str,
        user_id: int,
    ) -> Dict:
        """
        Process multimodal items through the pipeline.
        Inspired by RAG-Anything's _process_multimodal_content_batch_type_aware.
        """
        result = {"items_processed": 0, "entities_added": 0, "relations_added": 0}

        try:
            manager = self._get_processor_manager()
            manager.set_content_source(content_list)

            # Process all multimodal items
            processed = manager.process_items_batch(multimodal_items, source_doc=filename)

            # Store multimodal chunks in ChromaDB
            chunks = []
            metadatas_list = []
            for i, proc_result in enumerate(processed):
                chunk = proc_result.get("chunk", "")
                if not chunk.strip():
                    continue

                chunks.append(chunk)
                metadatas_list.append({
                    "filename": filename,
                    "uploaded_by": username,
                    "user_id": user_id or 0,
                    "chunk_id": f"mm_{i}",
                    "content_type": proc_result.get("type", "unknown"),
                    "doc_id": str(doc_id),
                    "entity_name": proc_result.get("entity_info", {}).get("entity_name", ""),
                })

            if chunks:
                embeddings = self._embed_texts(chunks)
                ids = [f"{doc_id}_mm_{i}" for i in range(len(chunks))]
                self.multimodal_collection.add(
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=metadatas_list,
                    ids=ids,
                )
                result["items_processed"] = len(chunks)

            # Add multimodal entities to knowledge graph
            try:
                from .knowledge_graph import get_kg_engine
                kg_engine = get_kg_engine()
                for proc_result in processed:
                    entities = proc_result.get("entities", [])
                    relations = proc_result.get("relations", [])

                    for entity in entities:
                        name = entity.get("name", "").strip()
                        if not name:
                            continue
                        if not kg_engine.graph.has_node(name):
                            kg_engine.graph.add_node(
                                name,
                                type=entity.get("type", "CONCEPT"),
                                source_docs=[str(doc_id)],
                                source_files=[filename],
                                is_multimodal=True,
                            )
                        result["entities_added"] += 1

                    for rel in relations:
                        source = rel.get("source", "").strip()
                        target = rel.get("target", "").strip()
                        if source and target:
                            if not kg_engine.graph.has_node(source):
                                kg_engine.graph.add_node(source, type="CONCEPT", source_docs=[str(doc_id)], source_files=[filename])
                            if not kg_engine.graph.has_node(target):
                                kg_engine.graph.add_node(target, type="CONCEPT", source_docs=[str(doc_id)], source_files=[filename])
                            kg_engine.graph.add_edge(
                                source, target,
                                relation=rel.get("relation", "RELATED_TO"),
                                source_doc=str(doc_id),
                                source_file=filename,
                            )
                            result["relations_added"] += 1

                kg_engine.save()
            except Exception as e:
                print(f"KG multimodal entity error (non-fatal): {e}")

        except Exception as e:
            print(f"Multimodal pipeline error: {e}")
            traceback.print_exc()

        return result

    # ================================================================
    # Document Storage (ChromaDB)
    # ================================================================

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict],
        doc_id: str = None,
    ) -> Dict:
        """Add documents to ChromaDB collection."""
        try:
            if not texts:
                return {"status": "error", "message": "No texts provided"}

            embeddings = self._embed_texts(texts)
            ids = []
            for i, text in enumerate(texts):
                chunk_id = (
                    f"{doc_id}_chunk_{i}"
                    if doc_id
                    else f"chunk_{hashlib.md5(text.encode()).hexdigest()}"
                )
                ids.append(chunk_id)

            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )

            return {
                "status": "success",
                "num_chunks": len(texts),
                "collection_size": self.collection.count(),
            }
        except Exception as e:
            print(f"Error adding documents: {e}")
            return {"status": "error", "message": str(e)}

    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Dict = None,
        include_multimodal: bool = True,
    ) -> List[Dict]:
        """
        Search for similar documents.
        Optionally includes results from multimodal collection.
        """
        try:
            query_embedding = self._embed_texts([query])[0]
            results = []

            # Search main collection
            n = min(k, max(self.collection.count(), 1))
            if self.collection.count() > 0:
                main_results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n,
                    where=filter_metadata if filter_metadata else None,
                )
                if main_results["documents"] and main_results["documents"][0]:
                    for i, doc in enumerate(main_results["documents"][0]):
                        results.append({
                            "text": doc,
                            "metadata": main_results["metadatas"][0][i] if main_results["metadatas"] else {},
                            "distance": main_results["distances"][0][i] if main_results["distances"] else 0.0,
                            "id": main_results["ids"][0][i] if main_results["ids"] else None,
                            "source": "text",
                        })

            # Search multimodal collection
            if include_multimodal and self.multimodal_collection.count() > 0:
                mm_n = min(max(k // 2, 2), self.multimodal_collection.count())
                mm_results = self.multimodal_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=mm_n,
                    where=filter_metadata if filter_metadata else None,
                )
                if mm_results["documents"] and mm_results["documents"][0]:
                    for i, doc in enumerate(mm_results["documents"][0]):
                        results.append({
                            "text": doc,
                            "metadata": mm_results["metadatas"][0][i] if mm_results["metadatas"] else {},
                            "distance": mm_results["distances"][0][i] if mm_results["distances"] else 0.0,
                            "id": mm_results["ids"][0][i] if mm_results["ids"] else None,
                            "source": "multimodal",
                        })

            # Sort by distance (lower is better in cosine)
            results.sort(key=lambda x: x["distance"])
            return results[:k]

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def query_with_context(
        self,
        question: str,
        k: int = 5,
        graph_context: str = "",
        include_multimodal: bool = True,
    ) -> Dict:
        """
        Search for relevant context and generate an answer using the LLM.

        This is the main query method that:
        1. Searches both text and multimodal collections
        2. Combines vector search results with graph context
        3. Calls LLM to generate an answer
        """
        from .multimodal.prompts import PROMPTS

        # Search for relevant documents
        results = self.search(question, k=k, include_multimodal=include_multimodal)

        if not results:
            return {
                "answer": "I couldn't find any relevant information in the knowledge base to answer your question.",
                "sources": [],
                "num_sources": 0,
            }

        # Build context
        context_parts = []
        multimodal_parts = []
        sources = []

        for r in results:
            text = r["text"]
            metadata = r.get("metadata", {})
            source = r.get("source", "text")
            filename = metadata.get("filename", "Unknown")

            if source == "multimodal":
                multimodal_parts.append(f"[{metadata.get('content_type', 'content')} from {filename}]\n{text}")
            else:
                context_parts.append(f"[From: {filename}]\n{text}")

            if filename not in sources:
                sources.append(filename)

        context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No text context available."
        multimodal_str = "\n\n---\n\n".join(multimodal_parts) if multimodal_parts else ""

        # Build prompt
        prompt = PROMPTS["RAG_QUERY_WITH_CONTEXT"].format(
            context=context_str,
            graph_context=graph_context if graph_context else "",
            multimodal_context=f"\n=== MULTIMODAL CONTENT ===\n{multimodal_str}" if multimodal_str else "",
            question=question,
        )

        # Generate answer
        answer = self._generate_answer(PROMPTS["RAG_SYSTEM"], prompt)

        return {
            "answer": answer,
            "sources": sources,
            "num_sources": len(sources),
        }

    def _generate_answer(self, system_prompt: str, user_prompt: str) -> str:
        """Generate an answer using the LLM."""
        try:
            llm_client = self._get_llm_client()
            return llm_client.generate_text(system_prompt, user_prompt)
        except Exception as e:
            print(f"Answer generation error: {e}")
            return f"Error generating answer: {e}"

    # ================================================================
    # Delete Operations
    # ================================================================

    def delete_document_chunks(self, filename: str) -> int:
        """Delete all chunks for a document by filename."""
        count = 0
        try:
            # Delete from main collection
            self.collection.delete(where={"filename": filename})
            count += 1
        except Exception as e:
            print(f"Error deleting from main collection: {e}")

        try:
            # Delete from multimodal collection
            self.multimodal_collection.delete(where={"filename": filename})
            count += 1
        except Exception as e:
            print(f"Error deleting from multimodal collection: {e}")

        return count

    def delete_by_metadata(self, filter_metadata: Dict) -> bool:
        """Delete documents by metadata filter."""
        try:
            self.collection.delete(where=filter_metadata)
            try:
                self.multimodal_collection.delete(where=filter_metadata)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Error deleting: {e}")
            return False

    # ================================================================
    # Stats & Management
    # ================================================================

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        try:
            text_count = self.collection.count()
            mm_count = self.multimodal_collection.count()
            return {
                "total_documents": text_count + mm_count,
                "total_chunks": text_count,
                "text_chunks": text_count,
                "multimodal_chunks": mm_count,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model_name,
                "llm_model": self.llm_model,
                "vision_model": self.vision_model,
            }
        except Exception as e:
            return {"total_documents": 0, "total_chunks": 0, "llm_model": self.llm_model, "error": str(e)}

    def clear_all(self) -> bool:
        """Clear all documents from both collections."""
        try:
            self.client.delete_collection(name="documents")
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            self.client.delete_collection(name="multimodal_chunks")
            self.multimodal_collection = self.client.create_collection(
                name="multimodal_chunks",
                metadata={"hnsw:space": "cosine"},
            )
            return True
        except Exception as e:
            print(f"Error clearing collections: {e}")
            return False

    def get_multimodal_info(self) -> Dict:
        """Get information about multimodal processing capabilities."""
        return {
            "supported_formats": {
                "documents": [".pdf", ".docx", ".doc", ".txt", ".md"],
                "spreadsheets": [".xlsx", ".xls", ".csv"],
                "presentations": [".pptx", ".ppt"],
                "images": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"],
                "web": [".html", ".htm"],
            },
            "multimodal_processing": {
                "images": True,
                "tables": True,
                "equations": True,
            },
            "llm_model": self.llm_model,
            "vision_model": self.vision_model,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model_name,
        }


# ================================================================
# Singleton
# ================================================================
_enhanced_rag_engine: Optional[EnhancedRAGEngine] = None


def get_rag_engine() -> EnhancedRAGEngine:
    """Get or create the singleton enhanced RAG engine."""
    global _enhanced_rag_engine
    if _enhanced_rag_engine is None:
        _enhanced_rag_engine = EnhancedRAGEngine()
    return _enhanced_rag_engine
