# LightRAG v1.4.10 — Deep Source Code Analysis Report

> **Scope**: All core files in `LightRAG-main/lightrag/` including `lightrag.py`, `operate.py`, `base.py`, `types.py`, `constants.py`, `namespace.py`, `prompt.py`, `ollama.py`, `rerank.py`, `networkx_impl.py`, API server (`lightrag_server.py`, `config.py`, `utils_api.py`), and all router files (`document_routes.py`, `query_routes.py`, `graph_routes.py`, `ollama_api.py`).

---

## Table of Contents

- [A. LightRAG Class Architecture](#a-lightrag-class-architecture)
- [B. Query Modes & Pipeline](#b-query-modes--pipeline)
- [C. Entity & Relationship Extraction](#c-entity--relationship-extraction)
- [D. Knowledge Graph Operations](#d-knowledge-graph-operations)
- [E. Ollama Integration](#e-ollama-integration)
- [F. Reranking System](#f-reranking-system)
- [G. API Server & Routes](#g-api-server--routes)
- [H. Document Processing Pipeline](#h-document-processing-pipeline)
- [I. Prompt Templates](#i-prompt-templates)
- [J. Key Data Structures](#j-key-data-structures)

---

## A. LightRAG Class Architecture

### File: `lightrag.py` (4080 lines)

The central orchestrator is a **frozen dataclass** decorated with `@final`:

```python
@final
@dataclass
class LightRAG:
```

### A.1 Configuration Fields (Dataclass Parameters)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `working_dir` | `str` | `"./lightrag_cache_{timestamp}"` | Root storage directory |
| `workspace` | `str` | `""` | Multi-tenant namespace isolation |
| `llm_model_func` | `callable` | `None` | LLM completion function |
| `llm_model_name` | `str` | `""` | Model name for logging |
| `llm_model_max_async` | `int` | `4` | Max concurrent LLM calls |
| `llm_model_kwargs` | `dict` | `{}` | Extra kwargs for LLM |
| `embedding_func` | `EmbeddingFunc` | `None` | Embedding function wrapper |
| `embedding_batch_num` | `int` | `32` | Batch size for embeddings |
| `embedding_func_max_async` | `int` | `16` | Max concurrent embedding calls |
| `kv_storage` | `str` | `"JsonKVStorage"` | KV storage backend class name |
| `vector_storage` | `str` | `"NanoVectorDBStorage"` | Vector DB backend class name |
| `graph_storage` | `str` | `"NetworkXStorage"` | Graph storage backend class name |
| `doc_status_storage` | `str` | `"JsonDocStatusStorage"` | Document status tracker |
| `chunk_token_size` | `int` | `1200` | Chunk size in tokens |
| `chunk_overlap_token_size` | `int` | `100` | Overlap between chunks |
| `entity_extract_max_gleaning` | `int` | `1` | Extra extraction passes |
| `entity_summary_to_max_tokens` | `int` | `500` | Summary max tokens |
| `max_parallel_insert` | `int` | `2` | Parallel document processing |
| `enable_llm_cache` | `bool` | `True` | Cache query LLM responses |
| `enable_llm_cache_for_entity_extract` | `bool` | `True` | Cache extraction LLM responses |
| `rerank_model_func` | `callable` | `None` | Reranking function |
| `addon_params` | `dict` | `{}` | Extra params (language, entity_types) |
| `default_llm_timeout` | `int` | `200` | LLM timeout seconds |
| `default_embedding_timeout` | `int` | `200` | Embedding timeout seconds |

### A.2 Storage Instances (Created in `__post_init__`)

The `__post_init__` method (lines ~400-700) creates **12 storage instances**:

```python
# KV Stores (BaseKVStorage)
self.full_docs          # NameSpace.KV_STORE_FULL_DOCS — full document text
self.text_chunks        # NameSpace.KV_STORE_TEXT_CHUNKS — chunked text
self.llm_response_cache # NameSpace.KV_STORE_LLM_RESPONSE_CACHE — LLM cache

# Entity/Relation KV (BaseKVStorage)  
self.full_entities      # NameSpace.KV_STORE_FULL_ENTITIES — merged entity data
self.full_relations     # NameSpace.KV_STORE_FULL_RELATIONS — merged relation data
self.entity_chunks      # NameSpace.KV_STORE_ENTITY_CHUNKS — entity→chunk mapping
self.relation_chunks    # NameSpace.KV_STORE_RELATION_CHUNKS — relation→chunk mapping

# Vector DBs (BaseVectorStorage)
self.entities_vdb       # NameSpace.VECTOR_STORE_ENTITIES — entity embeddings
self.relationships_vdb  # NameSpace.VECTOR_STORE_RELATIONSHIPS — relation embeddings
self.chunks_vdb         # NameSpace.VECTOR_STORE_CHUNKS — chunk embeddings

# Graph (BaseGraphStorage)
self.chunk_entity_relation_graph  # NameSpace.GRAPH_STORE — NetworkX graph

# Document Status (DocStatusStorage)
self.doc_status         # NameSpace.KV_STORE_DOC_STATUS_FULL — processing status
```

### A.3 Storage Backend Resolution

Storage classes are resolved dynamically via the `STORAGES` registry:

```python
from lightrag.kg.shared_storage import STORAGES

kv_storage_cls = STORAGES[self.kv_storage]           # "JsonKVStorage" → class
vector_storage_cls = STORAGES[self.vector_storage]   # "NanoVectorDBStorage" → class
graph_storage_cls = STORAGES[self.graph_storage]     # "NetworkXStorage" → class
doc_storage_cls = STORAGES[self.doc_status_storage]  # "JsonDocStatusStorage" → class
```

Supported backends include: `JsonKVStorage`, `NanoVectorDBStorage`, `NetworkXStorage`, `JsonDocStatusStorage`, `Neo4jStorage`, `MilvusStorage`, `PostgreSQLStorage`, etc.

### A.4 Rate Limiting & Concurrency

```python
# LLM rate limiting — wraps llm_model_func
self.llm_model_func = priority_limit_async_func_call(
    self.llm_model_func,
    max_async=self.llm_model_max_async    # default 4
)

# Embedding rate limiting  
self.embedding_func = priority_limit_async_func_call(
    self.embedding_func,
    max_async=self.embedding_func_max_async  # default 16
)
```

`priority_limit_async_func_call` uses `asyncio.PriorityQueue` to support priority-based scheduling (higher priority calls like queries get processed before extraction calls).

### A.5 Lifecycle Methods

```python
async def initialize_storages(self)    # Initialize all 12 storage backends
async def finalize_storages(self)      # Persist and cleanup all storages
async def check_and_migrate_data(self) # Auto-migrate between storage versions
```

### A.6 Sync/Async Pattern

Every public method has paired sync/async versions:

```python
# Async (primary implementation)
async def ainsert(self, input, ...) -> dict
async def aquery(self, query, ...) -> QueryResult | str
async def adelete_by_doc_id(self, doc_id) -> DeletionResult

# Sync (wrapper using event loop)
def insert(self, input, ...) -> dict:
    loop = always_get_an_event_loop()
    return loop.run_until_complete(self.ainsert(input, ...))
```

---

## B. Query Modes & Pipeline

### B.1 Six Query Modes

| Mode | Entity Source | Relation Source | Chunks | Description |
|------|-------------|-----------------|--------|-------------|
| `local` | Vector search on entities_vdb | Edges connected to found entities | Entity-linked chunks | Entity-centric retrieval |
| `global` | Entities connected to found relations | Vector search on relationships_vdb | Relation-linked chunks | Relationship-centric retrieval |
| `hybrid` | Both local + global entities | Both local + global relations | Both sources merged | Combined approach |
| `naive` | None | None | Direct vector search on chunks_vdb | Simple RAG (no KG) |
| `mix` | Hybrid entities | Hybrid relations | Hybrid + vector chunks | KG + vector search combined |
| `bypass` | None | None | None | Direct LLM call, no retrieval |

### B.2 Query Entry Points

```python
# High-level API (backward compatible)
async def aquery(self, query, param=QueryParam()) -> QueryResult | str

# Structured data only (no LLM generation)
async def aquery_data(self, query, param) -> dict
    # Returns: {status, message, data: {entities, relationships, chunks, references}, metadata}

# Full query with LLM response
async def aquery_llm(self, query, param) -> dict
    # Returns: {llm_response: {content|response_iterator, is_streaming}, data: {...}, metadata: {...}}
```

### B.3 Four-Stage Query Architecture (`_build_query_context`)

**Stage 1 — Search** (`_perform_kg_search`):
```
Query → extract_keywords() → {hl_keywords, ll_keywords}
  ├── local search:  _get_node_data(ll_keywords) → entities + connected edges
  ├── global search: _get_edge_data(hl_keywords) → edges + connected entities
  ├── vector search: _get_vector_context(query) → chunks (for mix mode)
  └── Round-robin merge: interleave results from all search types
```

**Stage 2 — Truncate** (`_apply_token_truncation`):
```
Entities → truncate_list_by_token_size(max_entity_tokens=6000)
Relations → truncate_list_by_token_size(max_relation_tokens=8000)
```

**Stage 3 — Merge Chunks** (`_merge_all_chunks`):
```
Entity chunks:   _find_related_text_unit_from_entities()
Relation chunks: _find_related_text_unit_from_relations()
Vector chunks:   from Stage 1
→ Round-robin deduplication merge
```

**Stage 4 — Build Context** (`_build_context_str`):
```
Dynamic token budget:
  available_chunk_tokens = max_total_tokens(30000) - sys_prompt - kg_context - query - buffer(200)
  
→ process_chunks_unified() with reranking
→ generate_reference_list_from_chunks()
→ Format using kg_query_context template
→ Returns: (context_string, raw_data_dict)
```

### B.4 Keyword Extraction

```python
async def extract_keywords_only(query, global_config, hashing_kv):
    """LLM-based keyword extraction with caching"""
    # Uses PROMPTS["keywords_extraction"] template
    # Returns: {"high_level_keywords": [...], "low_level_keywords": [...]}
    # Caching: MD5 hash of (mode, query) → stored in llm_response_cache
```

### B.5 Naive Query (Standalone)

```python
async def naive_query(query, chunks_vdb, query_param, global_config, ...):
    """Pure vector search without knowledge graph"""
    # 1. Vector search: chunks_vdb.query(query, top_k)
    # 2. Dynamic token allocation
    # 3. process_chunks_unified() with optional reranking
    # 4. Format using naive_query_context template
    # 5. LLM generation with caching
    # Returns: QueryResult
```

### B.6 Chunk Selection Methods

Two configurable chunk selection strategies (set via `kg_chunk_pick_method`):

```python
# WEIGHT method (default): Linear gradient weighted polling
pick_by_weighted_polling(entities_with_chunks, max_related_chunks, min_related_chunks=1)

# VECTOR method: Cosine similarity-based selection
pick_by_vector_similarity(query, text_chunks_storage, chunks_vdb, num_of_chunks, ...)
```

---

## C. Entity & Relationship Extraction

### C.1 Entry Point: `extract_entities()`

```python
async def extract_entities(
    chunks: dict[str, dict],      # {chunk_id: {"content": str, "full_doc_id": str, ...}}
    knowledge_graph_inst,          # BaseGraphStorage
    entity_vdb,                    # BaseVectorStorage  
    relationships_vdb,             # BaseVectorStorage
    global_config: dict,           # Contains llm_model_func, entity_types, etc.
    pipeline_status: dict = None,  # For progress tracking
) -> dict[str, dict]:            # {chunk_id: extraction_results}
```

**Processing per chunk:**

1. **Format prompt** using `entity_extraction_system_prompt` + `entity_extraction_user_prompt`
   - Injects `entity_types` (default: `"organization,person,geo,event"`)
   - Includes 3 detailed examples via `entity_extraction_examples`

2. **LLM call** with caching (cache key = MD5 of chunk content)

3. **Gleaning** (up to `MAX_GLEANING=1` extra passes):
   - Uses `entity_continue_extraction_user_prompt`
   - Appends results to original extraction

4. **Parse results** via `_process_extraction_result()`:
   - Splits by `DEFAULT_COMPLETION_DELIMITER` (`<|COMPLETE|>`)
   - Splits records by `DEFAULT_RECORD_DELIMITER` (`##`)
   - For each record, splits by `DEFAULT_TUPLE_DELIMITER` (`<|#|>`)
   - **Entity**: 4 fields → `(type="entity", name, entity_type, description)`
   - **Relationship**: 5 fields → `(type="relation", source, target, description, keywords)`

### C.2 Entity Record Format

```
("entity"<|#|>ENTITY_NAME<|#|>ENTITY_TYPE<|#|>DESCRIPTION)##
```

Parsed into:
```python
{
    "entity_name": "uppercase_name",    # Always uppercased
    "entity_type": "ORGANIZATION",
    "description": "Description text",
    "source_id": "chunk_id1<SEP>chunk_id2",
}
```

### C.3 Relationship Record Format

```
("relation"<|#|>SOURCE_ENTITY<|#|>TARGET_ENTITY<|#|>DESCRIPTION<|#|>KEYWORDS)##
```

Parsed into:
```python
{
    "src_id": "SOURCE_ENTITY",
    "tgt_id": "TARGET_ENTITY", 
    "description": "Relationship description",
    "keywords": "keyword1, keyword2",
    "weight": 1.0,
    "source_id": "chunk_id1<SEP>chunk_id2",
}
```

### C.4 Merge Pipeline: `merge_nodes_and_edges()`

Three-phase merge process:

**Phase 1 — Merge Entities** (`_merge_nodes_then_upsert`):
```
For each entity_name:
1. Acquire entity-level lock (get_storage_keyed_lock)
2. Get existing entity from graph
3. Merge source_ids (FIFO or KEEP strategy, max 10 by default)
4. Deduplicate descriptions (set-based)
5. If too many descriptions → LLM map-reduce summarization
6. Compute file_path from source chunk metadata  
7. Upsert to graph storage (chunk_entity_relation_graph)
8. Upsert to vector DB (entities_vdb) with embedding
9. Upsert to entity_chunks storage
```

**Phase 2 — Merge Relations** (`_merge_edges_then_upsert`):
```
Same 11-step process as entities, additionally:
- Accumulates weight across merges
- Keywords are merged/deduplicated
- Sorts edge by alphabetical order of (src, tgt)
```

**Phase 3 — Update Full Storage**:
```
Update full_entities and full_relations KV stores
with merged entity/relation data
```

### C.5 Description Summarization

```python
async def _handle_entity_relation_summary(entity_or_relation_name, description, ...):
    """Map-reduce summarization when descriptions exceed context window"""
    # Uses PROMPTS["summarize_entity_descriptions"]
    # Max context: summary_context_size (configurable)
    # Max output: summary_max_tokens (configurable)
```

---

## D. Knowledge Graph Operations

### D.1 NetworkX Storage (`networkx_impl.py`, 570 lines)

```python
class NetworkXStorage(BaseGraphStorage):
    """Undirected graph storage using NetworkX + GraphML persistence"""
```

**Storage Format**: GraphML XML files at `{working_dir}/{workspace}/graph_{namespace}.graphml`

**Cross-Process Sync**:
- Uses `update_flag` in shared storage to notify other processes of changes
- `_check_update_flag()` reloads graph from disk if another process modified it
- `get_storage_keyed_lock()` for entity-level concurrent access

### D.2 Graph CRUD Operations

```python
# Node operations
async def upsert_node(node_id, node_data)    # Create/update node
async def has_node(node_id) -> bool
async def get_node(node_id) -> dict | None
async def delete_node(node_id)
async def remove_nodes(node_ids: list)        # Bulk delete

# Edge operations (undirected)
async def upsert_edge(src, tgt, edge_data)   # Create/update edge
async def has_edge(src, tgt) -> bool
async def get_edge(src, tgt) -> dict | None
async def remove_edges(edges: list[tuple])    # Bulk delete  

# Batch operations (optimized)
async def get_nodes_batch(node_ids) -> dict
async def get_edges_batch(edge_pairs) -> dict
async def node_degrees_batch(node_ids) -> dict
async def edge_degrees_batch(edge_pairs) -> dict
async def get_nodes_edges_batch(node_ids) -> dict  # All edges for nodes
```

### D.3 Knowledge Graph BFS Traversal

```python
async def get_knowledge_graph(node_label, max_depth=3, max_nodes=1000):
    """BFS traversal with degree-based prioritization"""
    # 1. Find start node by exact label match (case-insensitive)
    # 2. BFS: priority queue sorted by (-degree, node_id)
    # 3. At each depth level, expand highest-degree nodes first
    # 4. Stop when max_depth or max_nodes reached
    # 5. Returns: KnowledgeGraph(nodes, edges, is_truncated)
```

### D.4 Label Search

```python
async def get_all_labels()          # All node IDs
async def get_popular_labels(limit) # Sorted by degree (most connected first)
async def search_labels(query, limit):
    """Fuzzy label search with relevance scoring"""
    # Scoring: exact_match > starts_with > substring > word_match
    # Case-insensitive comparison
```

### D.5 Entity/Relation Editing (via `utils_graph.py`)

```python
# High-level operations delegated to utils_graph
async def aedit_entity(entity_name, updated_data, allow_rename, allow_merge)
async def aedit_relation(source, target, updated_data)
async def acreate_entity(entity_name, entity_data)
async def acreate_relation(source, target, relation_data)
async def amerge_entities(source_entities, target_entity, merge_strategy, ...)
```

### D.6 Deletion System (`adelete_by_doc_id`)

**10-Step Deletion Process:**

```
Step 1:  Get document status from doc_status storage
Step 2:  Get all chunk IDs belonging to the document  
Step 3:  Analyze affected entities (which reference deleted chunks)
Step 4:  Analyze affected relations (which reference deleted chunks)
Step 5:  Delete chunks from text_chunks KV and chunks_vdb
Step 6:  Delete entity→chunk mappings from entity_chunks
Step 7:  Delete relation→chunk mappings from relation_chunks
Step 8:  For each affected relation:
         - If ALL source chunks deleted → remove from graph + VDB
         - If some remain → rebuild from remaining chunks via rebuild_knowledge_from_chunks()
Step 9:  For each affected entity:
         - Same logic as Step 8
Step 10: Delete document from full_docs + doc_status
         Returns: DeletionResult(status, doc_id, message, file_path)
```

---

## E. Ollama Integration

### E.1 LLM Completion (`ollama.py`)

```python
async def _ollama_model_if_cache(
    model,                  # e.g., "mistral-nemo:latest"
    prompt,
    system_prompt=None,
    history_messages=[],
    keyword_extraction=False,
    **kwargs
) -> str | AsyncGenerator:
```

**Key features:**
- **Retry logic**: 3 attempts with exponential backoff
- **Streaming**: Returns `AsyncGenerator` when `stream=True`
- **Cloud detection**: Auto-detects cloud-hosted models (URLs containing `api.`, `.ai`, etc.)
- **API key**: Reads from `OLLAMA_API_KEY` env var or `api_key` kwarg
- **Timeout**: Configurable via `timeout` kwarg (default 200s)
- **Format**: Uses `format="json"` for keyword extraction

```python
def ollama_model_complete(prompt, system_prompt=None, **kwargs):
    """Wrapper that extracts model_name from global_config"""
    # Gets model from kwargs["hashing_kv"].global_config["llm_model_name"]
    # Passes all kwargs to _ollama_model_if_cache
```

### E.2 Ollama Embeddings

```python
@wrap_embedding_func_with_attrs(
    embedding_dim=1024, 
    max_token_size=8192, 
    model_name="bge-m3:latest"
)
async def ollama_embed(texts, embed_model=None, host=None, api_key=None, **kwargs):
    """Embed texts using Ollama API"""
    # Uses ollama.AsyncClient.embed()
    # Default model: bge-m3:latest (1024 dimensions)
    # Returns: numpy array of embeddings
```

### E.3 Server-Side Ollama Emulation (`ollama_api.py`, 724 lines)

LightRAG can **emulate an Ollama server** for compatibility with tools like Open WebUI:

```python
class OllamaAPI:
    """Exposes LightRAG as an Ollama-compatible API"""
    
    # Routes mounted at /api prefix:
    # GET  /api/version    → OllamaVersionResponse
    # GET  /api/tags       → Available "models" (faked as LightRAG)
    # GET  /api/ps         → Running models
    # POST /api/generate   → Direct LLM completion (bypass RAG)
    # POST /api/chat       → LightRAG query via chat interface
```

**Chat Query Mode Parsing** (`parse_query_mode`):
```
"/local query"       → SearchMode.local, only_need_context=False
"/global query"      → SearchMode.global_, only_need_context=False
"/hybrid query"      → SearchMode.hybrid
"/naive query"       → SearchMode.naive
"/mix query"         → SearchMode.mix (default)
"/bypass query"      → Direct LLM, no RAG
"/context query"     → SearchMode.mix, only_need_context=True
"/localcontext ..."  → SearchMode.local, only_need_context=True
"/[prompt] query"    → Custom user_prompt via bracket syntax
```

---

## F. Reranking System

### File: `rerank.py` (578 lines)

### F.1 Architecture

```
Query + Retrieved Chunks
    ↓
chunk_documents_for_rerank()     # Split long docs into rerank-friendly chunks
    ↓
generic_rerank_api()             # Call rerank API (Cohere/Jina/Aliyun)
    ↓
aggregate_chunk_scores()         # Merge chunk scores back to document level
    ↓
Sorted & filtered chunks         # Ordered by relevance score
```

### F.2 Chunking for Rerank

```python
def chunk_documents_for_rerank(documents, max_tokens=4096, overlap_tokens=128):
    """Split documents exceeding max_tokens into overlapping chunks"""
    # Each chunk mapped back to original document index
    # Returns: (chunked_docs, chunk_map, max_doc_tokens)
```

### F.3 Generic Rerank API

```python
async def generic_rerank_api(
    query,
    documents,
    top_n=None,
    model=None,
    base_url=None,
    api_key=None,
    api_format="standard",       # "standard" (Cohere/Jina) or "aliyun"
    max_tokens_per_doc=4096,     # Auto-chunk if exceeded
    enable_chunking=False,
    extra_body=None,
):
    """Universal rerank with retry (3 attempts), chunking, and score aggregation"""
    # Returns: list of {index, relevance_score, document: {text}}
```

### F.4 Provider-Specific Functions

```python
# Cohere
async def cohere_rerank(query, documents, top_n=None, model="rerank-v3.5", 
                        base_url="https://api.cohere.com/v2/rerank", ...):
    """max_tokens: 4096"""

# Jina
async def jina_rerank(query, documents, top_n=None, 
                      model="jina-reranker-v2-base-multilingual",
                      base_url="https://api.jina.ai/v1/rerank", ...):

# Aliyun DashScope
async def ali_rerank(query, documents, top_n=None, 
                     model="gte-rerank-v2",
                     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/rerank", ...):
    """Uses api_format="aliyun" which wraps documents as [{"content": text}]"""
```

### F.5 Score Aggregation

```python
def aggregate_chunk_scores(chunk_results, chunk_map, method="max"):
    """Aggregate chunk-level rerank scores to document level"""
    # Methods: "max" (default), "mean", "first"
    # Returns scores mapped back to original document indices
```

---

## G. API Server & Routes

### G.1 Server Architecture (`lightrag_server.py`, 1531 lines)

```python
def create_app(args) -> FastAPI:
    """Factory function creating the FastAPI application"""
```

**Key components:**
- **FastAPI** with CORS, Swagger UI (offline static files), ReDoc
- **Lifespan management**: `rag.initialize_storages()` → yield → `rag.finalize_storages()`
- **Authentication**: Combined API key + OAuth2/JWT dependency
- **WebUI**: Static file serving from `lightrag/api/webui/` with smart caching

### G.2 LLM Binding Factory

```python
def create_llm_model_func(binding: str):
    """Creates LLM function based on binding type"""
    # Supports: lollms, ollama, openai, azure_openai, aws_bedrock, gemini
    # OpenAI/Azure/Gemini use "optimized" wrappers with pre-processed config
```

### G.3 Embedding Function Factory

```python
def create_optimized_embedding_function(config_cache, binding, model, host, api_key, args):
    """Creates EmbeddingFunc with proper dimension/token inheritance"""
    # Supports: openai, ollama, gemini, jina, azure_openai, aws_bedrock, lollms
    # Extracts max_token_size and embedding_dim from provider defaults
    # Returns EmbeddingFunc with send_dimensions flag for Jina/Gemini
```

### G.4 Configuration (`config.py`, 581 lines)

```python
def parse_args() -> argparse.Namespace:
    """100+ configuration parameters from CLI args + environment variables"""
```

Key configuration groups:
- **Server**: host, port, workers, timeout, SSL, CORS
- **Storage**: kv_storage, vector_storage, graph_storage, doc_status_storage
- **LLM**: llm_binding, llm_model, llm_binding_host, llm_binding_api_key
- **Embedding**: embedding_binding, embedding_model, embedding_dim, embedding_send_dim
- **Chunking**: chunk_size (1200), chunk_overlap_size (100)
- **Query**: top_k (40), chunk_top_k (20), max_entity/relation/total_tokens, cosine_threshold (0.2)
- **Rerank**: rerank_binding, rerank_model, min_rerank_score
- **Auth**: auth_accounts, token_secret, token_expire_hours, jwt_algorithm
- **Caching**: enable_llm_cache, enable_llm_cache_for_extract

**Global Args Proxy Pattern:**
```python
class _GlobalArgsProxy:
    """Auto-initializes config on first attribute access"""
    def __getattribute__(self, name):
        if not _initialized:
            initialize_config()
        return getattr(_global_args, name)

global_args = _GlobalArgsProxy()  # Module-level singleton
```

### G.5 Authentication (`utils_api.py`, 439 lines)

```python
def get_combined_auth_dependency(api_key):
    """Three-tier authentication:
    1. Whitelist paths (skip auth for /health, /api/*)
    2. OAuth2 JWT token validation with auto-renewal
    3. API key (X-API-Key header)
    """
```

**Token Auto-Renewal:**
- Sliding window: renews when remaining time < `token_renew_threshold` (default 50%)
- Rate-limited: minimum 60 seconds between renewals per user
- Skip paths: `/health`, `/documents/paginated`, `/documents/pipeline_status`
- New token returned via `X-New-Token` response header

### G.6 Route Groups

#### Document Routes (`document_routes.py`, 3291 lines)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/documents/scan` | `scan_for_new_documents` | Scan input directory for new files |
| POST | `/documents/upload` | `upload_to_input_dir` | Upload file → enqueue → process |
| POST | `/documents/text` | `insert_text` | Insert single text string |
| POST | `/documents/texts` | `insert_texts` | Insert multiple text strings |
| DELETE | `/documents` | `clear_documents` | Delete ALL documents + graph data |
| GET | `/documents/statuses` | `documents` | Get all document statuses grouped by status |
| GET | `/documents/pipeline_status` | `get_pipeline_status` | Current pipeline processing status |
| DELETE | `/documents/doc` | `delete_document` | Delete specific documents by ID |
| POST | `/documents/cache/clear` | `clear_cache` | Clear LLM response cache |
| DELETE | `/documents/entity` | `delete_entity` | Delete entity from KG |
| DELETE | `/documents/relation` | `delete_relation` | Delete relation from KG |
| GET | `/documents/track/{track_id}` | `get_track_status` | Track document processing by track_id |
| POST | `/documents/paginated` | `get_documents_paginated` | Paginated document listing |
| GET | `/documents/status_counts` | `get_document_status_counts` | Count by status |
| POST | `/documents/reprocess_failed` | `reprocess_failed_documents` | Retry failed documents |
| POST | `/documents/cancel_pipeline` | `cancel_pipeline` | Cancel running pipeline |

**Document Upload Flow:**
```
Upload file → sanitize_filename() → save to input_dir
→ Read content (PDF/DOCX/PPTX/XLSX/text parsing)
→ pipeline_enqueue_file(rag, content, file_path)
  → rag.apipeline_enqueue_documents([content])  # MD5 dedup
  → rag.apipeline_process_enqueue_documents()    # Background KG extraction
```

**Supported File Formats:**
- Text: `.txt`, `.md`, `.mdx`, `.csv`, `.json`, `.xml`, `.yaml`, `.yml`
- Documents: `.pdf` (pypdf), `.docx` (python-docx), `.pptx` (python-pptx), `.xlsx` (openpyxl)
- Rich text: `.rtf`, `.odt`, `.epub`, `.html`
- Code: `.py`, `.java`, `.js`, `.ts`, `.go`, `.rb`, `.php`, `.c`, `.cpp`, `.swift`
- Optional: DOCLING engine for advanced document parsing

#### Query Routes (`query_routes.py`, 1160 lines)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/query` | `query_text` | Non-streaming RAG query → `QueryResponse` |
| POST | `/query/stream` | `query_text_stream` | Streaming RAG query → NDJSON `StreamingResponse` |
| POST | `/query/data` | `query_data` | Structured data only (no LLM) → `QueryDataResponse` |

**QueryRequest parameters** (Pydantic model):
```python
class QueryRequest(BaseModel):
    query: str                      # Min 3 chars
    mode: Literal["local","global","hybrid","naive","mix","bypass"] = "mix"
    only_need_context: bool = None
    only_need_prompt: bool = None
    response_type: str = None       # "Multiple Paragraphs", "Bullet Points", etc.
    top_k: int = None               # Entity/relation retrieval count
    chunk_top_k: int = None         # Vector chunk count
    max_entity_tokens: int = None
    max_relation_tokens: int = None
    max_total_tokens: int = None
    hl_keywords: list[str] = []     # Override high-level keywords
    ll_keywords: list[str] = []     # Override low-level keywords
    conversation_history: list = None
    user_prompt: str = None
    enable_rerank: bool = None
    include_references: bool = True
    include_chunk_content: bool = False
    stream: bool = True
```

**Streaming Response Format (NDJSON):**
```json
{"references": [{"reference_id": "1", "file_path": "/doc.pdf"}]}
{"response": "First chunk of "}
{"response": "the answer..."}
```

#### Graph Routes (`graph_routes.py`, 689 lines)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/graph/label/list` | `get_graph_labels` | All node labels |
| GET | `/graph/label/popular` | `get_popular_labels` | Top labels by degree |
| GET | `/graph/label/search` | `search_labels` | Fuzzy label search |
| GET | `/graphs` | `get_knowledge_graph` | BFS subgraph retrieval |
| GET | `/graph/entity/exists` | `check_entity_exists` | Check if entity exists |
| POST | `/graph/entity/edit` | `update_entity` | Edit/rename/merge entity |
| POST | `/graph/relation/edit` | `update_relation` | Edit relation |
| POST | `/graph/entity/create` | `create_entity` | Create new entity |
| POST | `/graph/relation/create` | `create_relation` | Create new relation |
| POST | `/graph/entities/merge` | `merge_entities` | Merge multiple entities |

**Entity Edit with Merge:**
```python
class EntityUpdateRequest(BaseModel):
    entity_name: str
    updated_data: Dict[str, Any]
    allow_rename: bool = False    # Allow changing entity_name
    allow_merge: bool = False     # If rename target exists, merge into it
```

#### Ollama API Routes (`ollama_api.py`, 724 lines)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/version` | `get_version` | Emulated Ollama version |
| GET | `/api/tags` | `get_tags` | Available models |
| GET | `/api/ps` | `get_running_models` | Running models |
| POST | `/api/generate` | `generate` | Direct LLM completion |
| POST | `/api/chat` | `chat` | RAG-powered chat |

### G.7 Server-Level Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect → `/webui` or `/docs` |
| GET | `/auth-status` | Auth configuration + guest token |
| POST | `/login` | OAuth2 login |
| GET | `/health` | System health + full configuration |
| GET | `/docs` | Custom Swagger UI |
| GET | `/webui` | Frontend static files |

---

## H. Document Processing Pipeline

### H.1 Pipeline Overview

```
Document Input (text/file)
    ↓
MD5 Hash Dedup (compute_mdhash_id)
    ↓
Status: PENDING → doc_status storage
    ↓
Validation & consistency check
    ↓
Chunking (chunking_by_token_size)
    ↓
Status: PREPROCESSING → PREPROCESSED
    ↓
Entity Extraction (extract_entities per chunk)
    ↓  
Merge (merge_nodes_and_edges)
    ↓
Status: PROCESSED
    ↓
Storage persistence (index_done_callback)
```

### H.2 Document Enqueue (`apipeline_enqueue_documents`)

```python
async def apipeline_enqueue_documents(self, input_texts, file_paths=None):
    """Enqueue documents for processing"""
    # 1. Generate doc_id = MD5(content) for each text
    # 2. Check for duplicates against existing full_docs
    # 3. Store new docs in full_docs KV
    # 4. Set doc_status = PENDING
    # Returns: {enqueued: int, duplicated: int, total: int, track_id: str}
```

### H.3 Document Processing (`apipeline_process_enqueue_documents`)

```python
async def apipeline_process_enqueue_documents(self, track_id=None):
    """Process all PENDING documents"""
    # Uses asyncio.Semaphore(max_parallel_insert) for concurrency control
    # Per document:
    #   1. chunk text → text_chunks KV + chunks_vdb
    #   2. extract_entities() per chunk
    #   3. merge_nodes_and_edges() → graph + VDBs
    #   4. Update doc_status → PROCESSED
    # Supports PipelineCancelledException for graceful cancellation
```

### H.4 Chunking Strategy

```python
def chunking_by_token_size(
    content: str,
    overlap_token_size: int = 128,      # Default overlap
    max_token_size: int = 1024,          # Max tokens per chunk
    tiktoken_model: str = "gpt-4o",     # Tokenizer model
) -> list[dict]:
    """Split text into overlapping token-sized chunks"""
    # Each chunk: {"tokens": int, "content": str, "chunk_order_index": int, "full_doc_id": str}
    # Uses tiktoken for token counting
    # Overlap ensures context continuity across chunk boundaries
```

### H.5 File Content Extraction

The `DocumentManager` class handles file-type-specific extraction:

```python
# PDF:   pypdf.PdfReader (with decryption support)
# DOCX:  python-docx with table extraction in document order
# PPTX:  python-pptx shape text extraction
# XLSX:  openpyxl with tab-delimited format per sheet
# HTML:  beautifulsoup4
# Text:  Direct read with encoding detection
# Optional: DOCLING engine for advanced conversion to Markdown
```

### H.6 Document Status Tracking

```python
class DocStatus(str, Enum):
    PENDING = "pending"         # Enqueued, not yet processed
    PROCESSING = "processing"   # Currently being chunked/extracted
    PREPROCESSED = "preprocessed"  # Chunks created, awaiting KG extraction
    PROCESSED = "processed"     # Fully processed into KG
    FAILED = "failed"          # Processing error

class DocProcessingStatus:
    content_summary: str       # First 100 chars
    content_length: int
    file_path: str
    status: DocStatus
    created_at: datetime
    updated_at: datetime
    track_id: str              # Batch tracking ID
    chunks_count: int
    chunks_list: list[str]     # Chunk IDs
    error_msg: str
    metadata: dict
```

---

## I. Prompt Templates

### File: `prompt.py` (433 lines)

### I.1 Entity Extraction System Prompt

```python
PROMPTS["entity_extraction_system_prompt"] = """
-Goal-
Given a text document that is potentially relevant to this activity and a list of entity types, 
identify all entities of those types from the text and all relationships among the identified entities.

-Steps-
1. Identify all entities. For each identified entity, extract:
- entity_name: Name (capitalized)
- entity_type: One of [{entity_types}]
- entity_description: Comprehensive description

Format: ("entity"<|#|>ENTITY_NAME<|#|>ENTITY_TYPE<|#|>ENTITY_DESCRIPTION)

2. Identify relationships. For each pair, extract:
- source_entity, target_entity, relationship_description, relationship_keywords

Format: ("relation"<|#|>SOURCE<|#|>TARGET<|#|>DESCRIPTION<|#|>KEYWORDS)

3. Return output with ##COMPLETION## after each list
"""
```

### I.2 RAG Response Prompt

```python
PROMPTS["rag_response"] = """
---Role---
You are a helpful assistant responding to questions about data in the tables provided.

---Goal---
Generate a response of the target length and format that responds to the user's question, 
summarizing all information in the input data tables.

If you don't know the answer, just say so.

Points supported by data should list the relevant reference(s) using [reference_id] format.

---Target response length and format---
{response_type}

---User Customized Prompt---
{user_prompt}

Add sections and commentary to the response as appropriate for the length and format.
Properly escape any curly brackets in your answer.

---Real Data---
{context_data}
"""
```

### I.3 Context Formatting Templates

```python
# KG Query Context (for local/global/hybrid/mix modes)
PROMPTS["kg_query_context"] = """
## Entities
{entities_str}

## Relationships
{relations_str}

## Sources
{text_chunks_str}

## Reference List
{reference_list_str}
"""

# Naive Query Context (for naive mode)
PROMPTS["naive_query_context"] = """
## Sources
{text_chunks_str}

## Reference List
{reference_list_str}
"""
```

### I.4 Keyword Extraction Prompt

```python
PROMPTS["keywords_extraction"] = """
---Role---
You are a helpful assistant tasked with identifying both high-level and low-level 
keywords in the user's query.

---Goal---
Given the query, list high-level and low-level keywords. 
High-level keywords focus on overarching concepts or themes.
Low-level keywords focus on specific entities, details, or concrete terms.

---Instructions---
- Output in JSON with: {"high_level_keywords": [...], "low_level_keywords": [...]}
"""
```

### I.5 Delimiters

```python
DEFAULT_TUPLE_DELIMITER = "<|#|>"
DEFAULT_RECORD_DELIMITER = "##"  
DEFAULT_COMPLETION_DELIMITER = "<|COMPLETE|>"
GRAPH_FIELD_SEP = "<SEP>"           # Separator in source_id fields
PROMPTS["process_tickers"] = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
```

---

## J. Key Data Structures

### J.1 QueryParam (base.py)

```python
@dataclass
class QueryParam:
    mode: Literal["local","global","hybrid","naive","mix","bypass"] = "global"
    only_need_context: bool = False
    only_need_prompt: bool = False
    response_type: str = "Multiple Paragraphs"
    stream: bool = False
    top_k: int = DEFAULT_TOP_K                    # 40
    chunk_top_k: int = DEFAULT_CHUNK_TOP_K        # 20
    max_entity_tokens: int = DEFAULT_MAX_ENTITY_TOKENS    # 6000
    max_relation_tokens: int = DEFAULT_MAX_RELATION_TOKENS # 8000
    max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS       # 30000
    hl_keywords: list[str] = []     # High-level override keywords
    ll_keywords: list[str] = []     # Low-level override keywords
    conversation_history: list = None
    model_func: callable = None     # Override LLM function per-query
    user_prompt: str = None
    enable_rerank: bool = True
    include_references: bool = True
```

### J.2 QueryResult (base.py)

```python
@dataclass  
class QueryResult:
    content: str = None              # Non-streaming text response
    response_iterator: AsyncIterator = None  # Streaming response
    raw_data: dict = None            # {entities, relationships, chunks, references, metadata}
    is_streaming: bool = False

    @property
    def reference_list(self) -> list   # Extract references from raw_data
    @property
    def metadata(self) -> dict         # Extract metadata from raw_data
```

### J.3 QueryContextResult (base.py)

```python
@dataclass
class QueryContextResult:
    context: str           # Formatted LLM context string
    raw_data: dict         # Structured retrieval data
```

### J.4 KnowledgeGraph Types (types.py)

```python
@dataclass
class KnowledgeGraphNode:
    id: int
    labels: list[str]
    properties: dict[str, Any]

@dataclass  
class KnowledgeGraphEdge:
    id: int
    type: str
    source: int
    target: int
    properties: dict[str, Any]

@dataclass
class KnowledgeGraph:
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]
    is_truncated: bool = False

class GPTKeywordExtractionFormat(BaseModel):
    """Pydantic model for structured keyword extraction output"""
    high_level_keywords: list[str]
    low_level_keywords: list[str]
```

### J.5 Document Status (base.py)

```python
class DocStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PREPROCESSED = "preprocessed"
    PROCESSED = "processed"
    FAILED = "failed"

@dataclass
class DocProcessingStatus:
    content_summary: str
    content_length: int
    file_path: str
    status: DocStatus
    created_at: datetime
    updated_at: datetime
    track_id: str
    chunks_count: int = 0
    chunks_list: list = field(default_factory=list)
    error_msg: str = None
    metadata: dict = field(default_factory=dict)
```

### J.6 Storage Base Classes (base.py)

```python
class StorageNameSpace(ABC):
    """Abstract base for all storage backends"""
    namespace: str
    workspace: str
    global_config: dict
    async def initialize(self)
    async def finalize(self)
    async def index_done_callback(self)
    async def drop(self)

class BaseKVStorage(StorageNameSpace):
    async def get_by_id(self, id) -> dict | None
    async def get_by_ids(self, ids) -> list[dict | None]
    async def filter_keys(self, keys) -> set[str]
    async def upsert(self, data: dict[str, dict])
    async def delete(self, ids: list[str])

class BaseVectorStorage(StorageNameSpace):
    cosine_better_than_threshold: float = 0.2
    async def query(self, query, top_k) -> list[dict]
    async def upsert(self, data: dict[str, dict])
    async def delete_entity(self, entity_name)
    async def delete_entity_relation(self, src, tgt)

class BaseGraphStorage(StorageNameSpace):
    async def upsert_node(self, node_id, node_data)
    async def upsert_edge(self, src, tgt, edge_data)
    async def get_node(self, node_id) -> dict | None
    async def get_edge(self, src, tgt) -> dict | None
    async def has_node(self, node_id) -> bool
    async def has_edge(self, src, tgt) -> bool
    async def node_degree(self, node_id) -> int
    async def edge_degree(self, src, tgt) -> int
    async def get_node_edges(self, source) -> list[tuple]
    async def get_knowledge_graph(self, label, max_depth, max_nodes) -> KnowledgeGraph
    # + batch operations, label search, etc.
```

### J.7 DeletionResult (base.py)

```python
@dataclass
class DeletionResult:
    status: str          # "success" | "not_found" | "error"
    doc_id: str
    message: str
    status_code: int     # 200, 404, 500
    file_path: str = None
```

### J.8 Constants (constants.py)

```python
DEFAULT_TOP_K = 40
DEFAULT_CHUNK_TOP_K = 20
DEFAULT_MAX_ENTITY_TOKENS = 6000
DEFAULT_MAX_RELATION_TOKENS = 8000
DEFAULT_MAX_TOTAL_TOKENS = 30000
DEFAULT_COSINE_THRESHOLD = 0.2
DEFAULT_MAX_GLEANING = 1
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP_SIZE = 100
GRAPH_FIELD_SEP = "<SEP>"
DEFAULT_MAX_ASYNC = 4
DEFAULT_MAX_PARALLEL_INSERT = 2
DEFAULT_RELATED_CHUNK_NUMBER = 5
DEFAULT_HISTORY_TURNS = 3
DEFAULT_SUMMARY_MAX_TOKENS = 500
DEFAULT_EMBEDDING_BATCH_NUM = 32
DEFAULT_LLM_TIMEOUT = 200
DEFAULT_EMBEDDING_TIMEOUT = 200
DEFAULT_ENTITY_TYPES = "organization,person,geo,event"
DEFAULT_KG_CHUNK_PICK_METHOD = "WEIGHT"
DEFAULT_SOURCE_IDS_LIMIT = 10
DEFAULT_SOURCE_IDS_LIMIT_METHOD = "FIFO"  # or "KEEP"
```

### J.9 Namespace Constants (namespace.py)

```python
class NameSpace:
    KV_STORE_FULL_DOCS = "full_docs"
    KV_STORE_TEXT_CHUNKS = "text_chunks"
    KV_STORE_LLM_RESPONSE_CACHE = "llm_response_cache"
    KV_STORE_FULL_ENTITIES = "full_entities"
    KV_STORE_FULL_RELATIONS = "full_relations"
    KV_STORE_ENTITY_CHUNKS = "entity_chunks"
    KV_STORE_RELATION_CHUNKS = "relation_chunks"
    VECTOR_STORE_ENTITIES = "entities"
    VECTOR_STORE_RELATIONSHIPS = "relationships"
    VECTOR_STORE_CHUNKS = "chunks"
    GRAPH_STORE = "chunk_entity_relation"
    KV_STORE_DOC_STATUS_FULL = "doc_status"
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐      │
│  │ Document  │  │  Query   │  │  Graph   │  │  Ollama API   │      │
│  │  Routes   │  │  Routes  │  │  Routes  │  │  (Emulation)  │      │
│  └─────┬─────┘  └─────┬────┘  └────┬─────┘  └───────┬───────┘      │
│        └───────────────┼───────────┼────────────────┘               │
│                        ▼           ▼                                │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │                    LightRAG Class                        │       │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │       │
│  │  │ ainsert  │  │  aquery  │  │ adelete_by_doc_id  │    │       │
│  │  └────┬─────┘  └────┬─────┘  └─────────┬──────────┘    │       │
│  │       │              │                   │               │       │
│  │       ▼              ▼                   ▼               │       │
│  │  ┌─────────┐  ┌───────────┐  ┌──────────────────┐      │       │
│  │  │Chunking │  │ operate.  │  │  10-Step Delete  │      │       │
│  │  │         │  │ kg_query  │  │                  │      │       │
│  │  └────┬────┘  └─────┬─────┘  └────────┬─────────┘      │       │
│  │       ▼              │                  │               │       │
│  │  ┌──────────────┐    │                  │               │       │
│  │  │ extract_     │    │   ┌──────────────┘               │       │
│  │  │ entities     │    │   │                              │       │
│  │  └──────┬───────┘    │   │                              │       │
│  │         ▼            │   │                              │       │
│  │  ┌──────────────┐    │   │                              │       │
│  │  │merge_nodes_  │    │   │                              │       │
│  │  │and_edges     │    │   │                              │       │
│  │  └──────┬───────┘    │   │                              │       │
│  │         │            │   │                              │       │
│  └─────────┼────────────┼───┼──────────────────────────────┘       │
│            ▼            ▼   ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │                   Storage Layer                          │       │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │       │
│  │  │ KV Store│ │Vector DB │ │  Graph   │ │ Doc Status │  │       │
│  │  │ (JSON)  │ │(NanoVDB) │ │(NetworkX)│ │  (JSON)    │  │       │
│  │  └─────────┘ └──────────┘ └──────────┘ └────────────┘  │       │
│  └─────────────────────────────────────────────────────────┘       │
│            ▼            ▼          ▼              ▼                 │
│      .json files    .db files  .graphml files  .json files         │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐    ┌──────────────────┐
│   LLM Backend    │    │ Embedding Backend│
│ (Ollama/OpenAI/  │    │ (Ollama/OpenAI/  │
│  Gemini/Azure/   │    │  Jina/Gemini/    │
│  Bedrock/LoLLMs) │    │  Azure/Bedrock)  │
└──────────────────┘    └──────────────────┘
```

---

## Summary of Key Code Patterns

1. **Pluggable Storage**: All storage backends resolve via `STORAGES` registry dict, enabling swapping JSON↔PostgreSQL↔Neo4j without code changes.

2. **Priority Async Queue**: `priority_limit_async_func_call` wraps LLM functions with `asyncio.PriorityQueue`, allowing query-time calls (priority=5) to be served before extraction calls (priority=1).

3. **Entity-Level Locking**: `get_storage_keyed_lock(entity_name)` ensures concurrent extraction tasks don't corrupt entity merge operations.

4. **Round-Robin Merge**: Query results from different sources (entities, relations, vector) are interleaved rather than concatenated, ensuring balanced representation.

5. **Dynamic Token Budget**: The query pipeline dynamically calculates available tokens for chunks after reserving space for system prompt, KG context, and query tokens.

6. **LLM Response Caching**: Both extraction and query LLM responses are cached with MD5 keys, avoiding redundant API calls.

7. **Gleaning**: After initial entity extraction, the system makes additional LLM passes to catch missed entities, using `entity_continue_extraction_user_prompt`.

8. **Map-Reduce Summarization**: When entity descriptions exceed context limits, they're summarized in batches and then merged.

9. **Cross-Process Sync**: NetworkX storage uses update flags and file-based persistence for multi-process coordination.

10. **Ollama Emulation**: The API server can masquerade as an Ollama server, enabling drop-in compatibility with tools like Open WebUI.
