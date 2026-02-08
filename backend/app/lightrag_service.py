"""
LightRAG Service - Integration layer for LightRAG in LocalAIChatBox
Self-contained LightRAG engine using Ollama for LLM and embeddings.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, AsyncIterator, Union
from dataclasses import dataclass
from functools import partial

import numpy as np

logger = logging.getLogger("lightrag_service")

# ============================================================
# Ollama LLM function (adapted from lightrag/llm/ollama.py)
# ============================================================

async def ollama_llm_complete(
    prompt: str,
    system_prompt: str = None,
    history_messages: list = [],
    enable_cot: bool = False,
    **kwargs
) -> Union[str, AsyncIterator[str]]:
    """LLM completion using Ollama - adapted for LocalAIChatBox."""
    try:
        import ollama as ollama_lib
    except ImportError:
        raise RuntimeError("ollama package not installed. Run: pip install ollama")
    
    stream = kwargs.pop("stream", False)
    kwargs.pop("max_tokens", None)
    kwargs.pop("hashing_kv", None)
    host = kwargs.pop("host", None) or os.getenv("OLLAMA_HOST", "http://ollama:11434")
    timeout = kwargs.pop("timeout", None)
    if timeout == 0 or timeout is None:
        timeout = float(os.getenv("LLM_TIMEOUT", "1800"))  # 30min for CPU-only inference
    model = kwargs.pop("model", None) or os.getenv("LIGHTRAG_LLM_MODEL", "llama3.2:3b")
    kwargs.pop("api_key", None)
    kwargs.pop("keyword_extraction", None)
    
    # Build messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    
    client = ollama_lib.AsyncClient(host=host, timeout=timeout)
    try:
        # Limit context window to prevent OOM on memory-constrained servers
        num_ctx = int(os.getenv("LIGHTRAG_NUM_CTX", "4096"))
        options = kwargs.pop("options", {})
        if "num_ctx" not in options:
            options["num_ctx"] = num_ctx
        
        response = await client.chat(
            model=model, messages=messages, stream=stream,
            options=options, **kwargs
        )
        if stream:
            async def inner():
                try:
                    async for chunk in response:
                        yield chunk["message"]["content"]
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    raise
                finally:
                    try:
                        await client._client.aclose()
                    except Exception:
                        pass
            return inner()
        else:
            result = response["message"]["content"]
            return result
    except Exception as e:
        logger.error(f"Ollama LLM error: {e}")
        raise
    finally:
        if not stream:
            try:
                await client._client.aclose()
            except Exception:
                pass


async def ollama_embedding(
    texts: list[str],
    embed_model: str = None,
    **kwargs
) -> np.ndarray:
    """Embedding function using Ollama - adapted for LocalAIChatBox."""
    try:
        import ollama as ollama_lib
    except ImportError:
        raise RuntimeError("ollama package not installed")
    
    if embed_model is None:
        embed_model = os.getenv("LIGHTRAG_EMBED_MODEL", "nomic-embed-text:latest")
    host = kwargs.pop("host", None) or os.getenv("OLLAMA_HOST", "http://ollama:11434")
    timeout = kwargs.pop("timeout", None)
    
    embed_timeout = float(os.getenv("EMBED_TIMEOUT", "300"))  # 5min for embedding
    client = ollama_lib.AsyncClient(host=host, timeout=embed_timeout)
    try:
        data = await client.embed(model=embed_model, input=texts)
        return np.array(data["embeddings"])
    except Exception as e:
        logger.error(f"Ollama embedding error: {e}")
        raise
    finally:
        try:
            await client._client.aclose()
        except Exception:
            pass


# ============================================================
# LightRAG Service Wrapper
# ============================================================

class LightRAGService:
    """Singleton service managing the LightRAG engine instance."""
    
    _instance: Optional["LightRAGService"] = None
    _initialized: bool = False
    
    def __init__(self):
        self.rag = None
        self.working_dir = os.getenv("LIGHTRAG_WORKING_DIR", "/app/data/lightrag_storage")
        self.llm_model = os.getenv("LIGHTRAG_LLM_MODEL", "llama3.2:3b")
        self.embed_model = os.getenv("LIGHTRAG_EMBED_MODEL", "nomic-embed-text:latest")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        self._lock = asyncio.Lock()
    
    @classmethod
    def get_instance(cls) -> "LightRAGService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self) -> bool:
        """Initialize the LightRAG engine."""
        if self._initialized and self.rag is not None:
            return True
        
        async with self._lock:
            if self._initialized and self.rag is not None:
                return True
            
            try:
                from app.lightrag.lightrag import LightRAG
                from app.lightrag.base import QueryParam
                from app.lightrag.utils import EmbeddingFunc
                
                # Create working directory
                os.makedirs(self.working_dir, exist_ok=True)
                
                # Create embedding function wrapper
                embedding_func = EmbeddingFunc(
                    embedding_dim=768,  # nomic-embed-text dimension
                    max_token_size=8192,
                    func=partial(ollama_embedding, embed_model=self.embed_model, host=self.ollama_host)
                )
                
                # Create LLM function wrapper
                async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                    return await ollama_llm_complete(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        history_messages=history_messages,
                        model=self.llm_model,
                        host=self.ollama_host,
                        **kwargs
                    )
                
                # Initialize LightRAG
                self.rag = LightRAG(
                    working_dir=self.working_dir,
                    llm_model_func=llm_func,
                    llm_model_name=self.llm_model,
                    embedding_func=embedding_func,
                    # Storage backends
                    kv_storage="JsonKVStorage",
                    vector_storage="NanoVectorDBStorage",
                    graph_storage="NetworkXStorage",
                    doc_status_storage="JsonDocStatusStorage",
                    # Chunking config
                    chunk_token_size=int(os.getenv("LIGHTRAG_CHUNK_SIZE", "800")),
                    chunk_overlap_token_size=int(os.getenv("LIGHTRAG_CHUNK_OVERLAP", "100")),
                    # Entity extraction 
                    entity_extract_max_gleaning=0,  # No re-extraction (faster)
                    # Query defaults
                    max_graph_nodes=int(os.getenv("LIGHTRAG_MAX_GRAPH_NODES", "1000")),
                    # LLM settings - reduced for CPU-only VPS
                    llm_model_max_async=1,
                    embedding_batch_num=5,
                    embedding_func_max_async=2,
                    enable_llm_cache=True,
                    addon_params={
                        "language": os.getenv("LIGHTRAG_LANGUAGE", "Vietnamese"),
                        "entity_types": ["PERSON", "ORGANIZATION", "TECHNOLOGY", "CONCEPT", "EVENT", "LOCATION", "PROJECT", "PRODUCT"],
                    }
                )
                
                # Initialize storages
                await self.rag.initialize_storages()
                
                self._initialized = True
                logger.info(f"LightRAG initialized: working_dir={self.working_dir}, llm={self.llm_model}, embed={self.embed_model}")
                return True
                
            except Exception as e:
                logger.error(f"LightRAG initialization failed: {e}", exc_info=True)
                self.rag = None
                self._initialized = False
                return False
    
    async def insert_text(self, text: str, file_path: str = None) -> dict:
        """Insert text into LightRAG for indexing (non-blocking)."""
        if not self._initialized:
            await self.initialize()
        
        try:
            from app.lightrag.utils import generate_track_id
            track_id = generate_track_id("insert")
            
            # Enqueue document (fast, no LLM calls)
            await self.rag.apipeline_enqueue_documents(
                text,
                ids=None,
                file_paths=[file_path] if file_path else None,
                track_id=track_id
            )
            
            # Process in background (entity extraction via LLM — can take minutes on CPU)
            async def _process_bg():
                try:
                    await self.rag.apipeline_process_enqueue_documents()
                    logger.info(f"Background processing completed for track_id={track_id}")
                except Exception as e:
                    logger.error(f"Background processing error: {e}")
            
            asyncio.create_task(_process_bg())
            
            return {"status": "success", "track_id": track_id}
        except Exception as e:
            logger.error(f"Insert error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def insert_file(self, file_path: str) -> dict:
        """Insert a file into LightRAG (reads and indexes the content)."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Read file content
            path = Path(file_path)
            if not path.exists():
                return {"status": "error", "message": f"File not found: {file_path}"}
            
            content = ""
            suffix = path.suffix.lower()
            
            if suffix in [".txt", ".md", ".csv"]:
                content = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".pdf":
                try:
                    import fitz
                    doc = fitz.open(str(path))
                    content = "\n".join([page.get_text() for page in doc])
                    doc.close()
                except Exception:
                    content = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix in [".docx"]:
                try:
                    from docx import Document
                    doc = Document(str(path))
                    content = "\n".join([p.text for p in doc.paragraphs])
                except Exception:
                    content = ""
            elif suffix in [".html", ".htm"]:
                try:
                    from bs4 import BeautifulSoup
                    html = path.read_text(encoding="utf-8", errors="ignore")
                    soup = BeautifulSoup(html, "lxml")
                    content = soup.get_text(separator="\n")
                except Exception:
                    content = path.read_text(encoding="utf-8", errors="ignore")
            else:
                content = path.read_text(encoding="utf-8", errors="ignore")
            
            if not content.strip():
                return {"status": "error", "message": "No content extracted from file"}
            
            from app.lightrag.utils import generate_track_id
            track_id = generate_track_id("insert")
            
            # Enqueue (fast)
            await self.rag.apipeline_enqueue_documents(
                content,
                ids=None,
                file_paths=[str(path.name)],
                track_id=track_id
            )
            
            # Process in background
            async def _process_bg():
                try:
                    await self.rag.apipeline_process_enqueue_documents()
                    logger.info(f"Background file processing completed for {path.name}")
                except Exception as e:
                    logger.error(f"Background file processing error: {e}")
            
            asyncio.create_task(_process_bg())
            
            return {"status": "success", "track_id": track_id, "chars": len(content)}
        except Exception as e:
            logger.error(f"File insert error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def query(
        self,
        question: str,
        mode: str = "hybrid",
        stream: bool = False,
        top_k: int = None,
        max_tokens: int = None,
        only_need_context: bool = False,
        only_need_prompt: bool = False,
        history_messages: list = None,
    ) -> Union[str, AsyncIterator[str], dict]:
        """Query LightRAG with various modes."""
        if not self._initialized:
            await self.initialize()
        
        try:
            from app.lightrag.base import QueryParam
            
            param = QueryParam(
                mode=mode,
                stream=stream,
                only_need_context=only_need_context,
                only_need_prompt=only_need_prompt,
                enable_rerank=False,
            )
            
            if top_k is not None:
                param.top_k = top_k
            if history_messages:
                param.conversation_history = history_messages
            
            result = await self.rag.aquery(question, param=param)
            
            if stream and hasattr(result, '__aiter__'):
                return result
            
            return result
            
        except Exception as e:
            logger.error(f"Query error: {e}")
            return f"Error: {str(e)}"
    
    async def query_with_context(
        self,
        question: str,
        mode: str = "hybrid",
        top_k: int = None,
    ) -> dict:
        """Query and return both context and response."""
        if not self._initialized:
            await self.initialize()
        
        try:
            from app.lightrag.base import QueryParam
            
            # First get context
            context_param = QueryParam(mode=mode, only_need_context=True, enable_rerank=False)
            if top_k:
                context_param.top_k = top_k
            context = await self.rag.aquery(question, param=context_param)
            
            # Then get full response
            response_param = QueryParam(mode=mode, enable_rerank=False)
            if top_k:
                response_param.top_k = top_k
            response = await self.rag.aquery(question, param=response_param)
            
            return {
                "response": response,
                "context": context,
                "mode": mode,
            }
        except Exception as e:
            logger.error(f"Query with context error: {e}")
            return {"response": f"Error: {str(e)}", "context": "", "mode": mode}
    
    async def get_graph_data(self, label: str = None, max_depth: int = 3, max_nodes: int = 1000) -> dict:
        """Get knowledge graph data for visualization."""
        if not self._initialized:
            await self.initialize()
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            
            if graph_storage is None:
                return {"nodes": [], "edges": []}
            
            # Get the underlying NetworkX graph
            nx_graph = await graph_storage._get_graph()
            if nx_graph is None:
                return {"nodes": [], "edges": []}
            
            nodes = []
            edges = []
            
            # Filter by label if specified
            target_nodes = set()
            if label:
                for node_id in nx_graph.nodes():
                    node_data = nx_graph.nodes[node_id]
                    entity_type = node_data.get("entity_type", "")
                    if label.lower() in entity_type.lower() or label.lower() in str(node_id).lower():
                        target_nodes.add(node_id)
                        # BFS expansion
                        visited = {node_id}
                        queue = [(node_id, 0)]
                        while queue and len(visited) < max_nodes:
                            current, depth = queue.pop(0)
                            if depth >= max_depth:
                                continue
                            for neighbor in nx_graph.neighbors(current):
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    queue.append((neighbor, depth + 1))
                        target_nodes = visited
                        break
            else:
                # Get all nodes up to max_nodes
                all_nodes = list(nx_graph.nodes())[:max_nodes]
                target_nodes = set(all_nodes)
            
            # Build nodes
            for node_id in target_nodes:
                node_data = nx_graph.nodes.get(node_id, {})
                nodes.append({
                    "id": str(node_id),
                    "label": str(node_id),
                    "entity_type": node_data.get("entity_type", "UNKNOWN"),
                    "description": node_data.get("description", ""),
                    "source_id": node_data.get("source_id", ""),
                })
            
            # Build edges
            for u, v, data in nx_graph.edges(data=True):
                if str(u) in {n["id"] for n in nodes} and str(v) in {n["id"] for n in nodes}:
                    edges.append({
                        "id": f"{u}->{v}",
                        "source": str(u),
                        "target": str(v),
                        "label": data.get("description", data.get("keywords", "")),
                        "weight": data.get("weight", 1.0),
                        "keywords": data.get("keywords", ""),
                        "description": data.get("description", ""),
                        "source_id": data.get("source_id", ""),
                    })
            
            return {
                "nodes": nodes,
                "edges": edges,
                "total_nodes": nx_graph.number_of_nodes(),
                "total_edges": nx_graph.number_of_edges(),
            }
        except Exception as e:
            logger.error(f"Get graph error: {e}")
            return {"nodes": [], "edges": [], "error": str(e)}
    
    async def get_graph_labels(self) -> list:
        """Get all unique entity types (labels) from the graph."""
        if not self._initialized:
            await self.initialize()
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            nx_graph = await graph_storage._get_graph()
            
            labels = set()
            for node_id in nx_graph.nodes():
                entity_type = nx_graph.nodes[node_id].get("entity_type", "UNKNOWN")
                labels.add(entity_type)
            
            return sorted(list(labels))
        except Exception as e:
            logger.error(f"Get labels error: {e}")
            return []
    
    async def search_entity(self, query: str) -> list:
        """Search for entities by name."""
        if not self._initialized:
            await self.initialize()
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            nx_graph = await graph_storage._get_graph()
            
            results = []
            query_lower = query.lower()
            for node_id in nx_graph.nodes():
                node_data = nx_graph.nodes[node_id]
                name = str(node_id).lower()
                desc = node_data.get("description", "").lower()
                
                if query_lower in name or query_lower in desc:
                    results.append({
                        "id": str(node_id),
                        "label": str(node_id),
                        "entity_type": node_data.get("entity_type", "UNKNOWN"),
                        "description": node_data.get("description", ""),
                    })
            
            return results[:50]  # Limit results
        except Exception as e:
            logger.error(f"Search entity error: {e}")
            return []
    
    async def edit_entity(self, entity_name: str, new_data: dict) -> dict:
        """Edit an entity's properties."""
        if not self._initialized:
            await self.initialize()
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            nx_graph = await graph_storage._get_graph()
            
            if entity_name not in nx_graph.nodes():
                return {"status": "error", "message": f"Entity '{entity_name}' not found"}
            
            # Update node data
            for key, value in new_data.items():
                nx_graph.nodes[entity_name][key] = value
            
            # Persist changes via index_done_callback
            await graph_storage.index_done_callback()
            
            return {"status": "success", "entity": entity_name}
        except Exception as e:
            logger.error(f"Edit entity error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def edit_relation(self, source: str, target: str, new_data: dict) -> dict:
        """Edit a relation's properties."""
        if not self._initialized:
            await self.initialize()
        
        try:
            graph_storage = self.rag.chunk_entity_relation_graph
            nx_graph = await graph_storage._get_graph()
            
            if not nx_graph.has_edge(source, target):
                return {"status": "error", "message": f"Edge '{source}' -> '{target}' not found"}
            
            # Update edge data
            for key, value in new_data.items():
                nx_graph.edges[source, target][key] = value
            
            # Persist changes
            await graph_storage.index_done_callback()
            
            return {"status": "success", "source": source, "target": target}
        except Exception as e:
            logger.error(f"Edit relation error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_document(self, doc_id: str) -> dict:
        """Delete a document from LightRAG."""
        if not self._initialized:
            await self.initialize()
        
        try:
            await self.rag.adelete_by_doc_id(doc_id=doc_id)
            return {"status": "success", "doc_id": doc_id}
        except Exception as e:
            logger.error(f"Delete doc error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_documents(self, status_filter: str = None) -> list:
        """Get all indexed documents with their status."""
        if not self._initialized:
            await self.initialize()
        
        try:
            doc_status = self.rag.doc_status
            if doc_status is None:
                return []
            
            # Use paginated API
            from app.lightrag.base import DocStatus
            filter_enum = None
            if status_filter:
                try:
                    filter_enum = DocStatus(status_filter)
                except (ValueError, KeyError):
                    pass
            
            docs_result, total = await doc_status.get_docs_paginated(
                status_filter=filter_enum,
                page=1,
                page_size=200,
                sort_field="updated_at",
                sort_direction="desc",
            )
            
            result = []
            for doc_id, doc_info in docs_result:
                result.append({
                    "id": doc_id,
                    "name": getattr(doc_info, 'file_path', doc_id),
                    "status": getattr(doc_info, 'status', 'unknown'),
                    "content_length": getattr(doc_info, 'content_length', 0),
                    "chunks_count": getattr(doc_info, 'chunks_count', 0),
                    "created_at": str(getattr(doc_info, 'created_at', '')),
                    "updated_at": str(getattr(doc_info, 'updated_at', '')),
                })
            
            return result
        except Exception as e:
            logger.error(f"Get documents error: {e}")
            return []
    
    async def get_pipeline_status(self) -> dict:
        """Get current pipeline processing status."""
        if not self._initialized:
            return {"busy": False, "status": "not_initialized"}
        
        try:
            from app.lightrag.kg.shared_storage import get_namespace_data
            status_data = get_namespace_data("pipeline_status", workspace=self.rag.workspace)
            if status_data:
                return {
                    "busy": status_data.get("busy", False),
                    "latest_message": status_data.get("latest_message", ""),
                    "history_messages": status_data.get("history_messages", [])[-10:],
                }
            return {"busy": False, "status": "idle"}
        except Exception as e:
            logger.debug(f"Pipeline status info: {e}")
            return {"busy": False, "status": "idle"}
    
    async def get_health(self) -> dict:
        """Get LightRAG service health status."""
        result = {
            "initialized": self._initialized,
            "working_dir": self.working_dir,
            "llm_model": self.llm_model,
            "embed_model": self.embed_model,
        }
        
        if self._initialized and self.rag:
            try:
                graph_storage = self.rag.chunk_entity_relation_graph
                nx_graph = await graph_storage._get_graph()
                result["graph_nodes"] = nx_graph.number_of_nodes()
                result["graph_edges"] = nx_graph.number_of_edges()
            except Exception:
                result["graph_nodes"] = 0
                result["graph_edges"] = 0
        
        return result
    
    async def clear_all(self) -> dict:
        """Clear all LightRAG data."""
        if not self._initialized:
            return {"status": "error", "message": "Not initialized"}
        
        try:
            # Get all document IDs using paginated API
            doc_status = self.rag.doc_status
            if doc_status:
                docs_result, total = await doc_status.get_docs_paginated(page=1, page_size=200)
                doc_ids = [doc_id for doc_id, _ in docs_result]
                for doc_id in doc_ids:
                    try:
                        await self.rag.adelete_by_doc_id(doc_id=doc_id)
                    except Exception as de:
                        logger.warning(f"Failed to delete doc {doc_id}: {de}")
            
            return {"status": "success", "message": "All data cleared"}
        except Exception as e:
            logger.error(f"Clear all error: {e}")
            return {"status": "error", "message": str(e)}


def get_lightrag_service() -> LightRAGService:
    """Get the singleton LightRAGService instance."""
    return LightRAGService.get_instance()
