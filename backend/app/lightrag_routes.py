"""
LightRAG API Routes for LocalAIChatBox
Provides REST API endpoints for LightRAG features: query, documents, graph, pipeline.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import os
import asyncio
import logging

from app.auth import get_current_user
from app.lightrag_service import get_lightrag_service

logger = logging.getLogger("lightrag_routes")
router = APIRouter(prefix="/api/lightrag", tags=["LightRAG"])


# ==================== Request/Response Models ====================

class LightRAGQueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # naive, local, global, hybrid, mix
    stream: bool = False
    top_k: Optional[int] = None
    only_need_context: bool = False
    only_need_prompt: bool = False
    history_turns: int = 0
    history_messages: Optional[list] = None


class LightRAGInsertTextRequest(BaseModel):
    text: str
    file_path: Optional[str] = None


class LightRAGInsertTextsRequest(BaseModel):
    texts: List[str]
    file_paths: Optional[List[str]] = None


class EntityEditRequest(BaseModel):
    entity_name: str
    description: Optional[str] = None
    entity_type: Optional[str] = None


class RelationEditRequest(BaseModel):
    source: str
    target: str
    description: Optional[str] = None
    keywords: Optional[str] = None
    weight: Optional[float] = None


class EntityExistsRequest(BaseModel):
    name: str


# ==================== HEALTH ====================

@router.get("/health")
async def lightrag_health():
    """Get LightRAG service health status."""
    service = get_lightrag_service()
    health = await service.get_health()
    return health


# ==================== QUERY ====================

@router.post("/query")
async def lightrag_query(req: LightRAGQueryRequest, user=Depends(get_current_user)):
    """Query LightRAG with specified mode (naive/local/global/hybrid/mix)."""
    service = get_lightrag_service()
    
    if not service._initialized:
        success = await service.initialize()
        if not success:
            raise HTTPException(status_code=503, detail="LightRAG not initialized")
    
    try:
        result = await service.query(
            question=req.query,
            mode=req.mode,
            stream=False,
            top_k=req.top_k,
            only_need_context=req.only_need_context,
            only_need_prompt=req.only_need_prompt,
            history_messages=req.history_messages,
        )
        return {"response": result, "mode": req.mode}
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def lightrag_query_stream(req: LightRAGQueryRequest, user=Depends(get_current_user)):
    """Stream query response from LightRAG (NDJSON format)."""
    service = get_lightrag_service()
    
    if not service._initialized:
        success = await service.initialize()
        if not success:
            raise HTTPException(status_code=503, detail="LightRAG not initialized")
    
    try:
        result = await service.query(
            question=req.query,
            mode=req.mode,
            stream=True,
            top_k=req.top_k,
            only_need_context=req.only_need_context,
            only_need_prompt=req.only_need_prompt,
            history_messages=req.history_messages,
        )
        
        if hasattr(result, '__aiter__'):
            async def generate():
                try:
                    async for chunk in result:
                        yield json.dumps({"chunk": chunk}) + "\n"
                    yield json.dumps({"done": True}) + "\n"
                except Exception as e:
                    yield json.dumps({"error": str(e)}) + "\n"
            
            return StreamingResponse(
                generate(),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            return {"response": result, "mode": req.mode}
    except Exception as e:
        logger.error(f"Stream query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/context")
async def lightrag_query_with_context(req: LightRAGQueryRequest, user=Depends(get_current_user)):
    """Query and return both context and response."""
    service = get_lightrag_service()
    
    if not service._initialized:
        await service.initialize()
    
    try:
        result = await service.query_with_context(
            question=req.query,
            mode=req.mode,
            top_k=req.top_k,
        )
        return result
    except Exception as e:
        logger.error(f"Query context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DOCUMENTS ====================

@router.get("/documents")
async def lightrag_get_documents(
    status: Optional[str] = None,
    user=Depends(get_current_user)
):
    """Get all indexed documents with optional status filter."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    docs = await service.get_documents(status_filter=status)
    return {"documents": docs, "total": len(docs)}


@router.post("/documents/text")
async def lightrag_insert_text(req: LightRAGInsertTextRequest, user=Depends(get_current_user)):
    """Insert text content into LightRAG for indexing."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    result = await service.insert_text(req.text, file_path=req.file_path)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/documents/texts")
async def lightrag_insert_texts(req: LightRAGInsertTextsRequest, user=Depends(get_current_user)):
    """Insert multiple texts into LightRAG."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    results = []
    for i, text in enumerate(req.texts):
        fp = req.file_paths[i] if req.file_paths and i < len(req.file_paths) else None
        result = await service.insert_text(text, file_path=fp)
        results.append(result)
    
    return {"results": results, "total": len(results)}


@router.post("/documents/upload")
async def lightrag_upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Upload and index a document file."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    # Save uploaded file
    upload_dir = "/app/data/lightrag_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        result = await service.insert_file(file_path)
        return result
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def lightrag_delete_document(doc_id: str, user=Depends(get_current_user)):
    """Delete a document from LightRAG index."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    result = await service.delete_document(doc_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("/documents")
async def lightrag_clear_documents(user=Depends(get_current_user)):
    """Clear all documents from LightRAG."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    result = await service.clear_all()
    return result


@router.get("/documents/pipeline_status")
async def lightrag_pipeline_status(user=Depends(get_current_user)):
    """Get pipeline processing status."""
    service = get_lightrag_service()
    status = await service.get_pipeline_status()
    return status


@router.get("/documents/status_counts")
async def lightrag_document_status_counts(user=Depends(get_current_user)):
    """Get document counts by status."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    docs = await service.get_documents()
    counts = {}
    for doc in docs:
        s = doc.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    counts["total"] = len(docs)
    return counts


# ==================== GRAPH ====================

@router.get("/graphs")
async def lightrag_get_graph(
    label: Optional[str] = None,
    max_depth: int = Query(default=3, ge=1, le=10),
    max_nodes: int = Query(default=1000, ge=1, le=10000),
    user=Depends(get_current_user)
):
    """Get knowledge graph data for visualization."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    data = await service.get_graph_data(label=label, max_depth=max_depth, max_nodes=max_nodes)
    return data


@router.get("/graph/label/list")
async def lightrag_get_labels(user=Depends(get_current_user)):
    """Get all entity type labels."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    labels = await service.get_graph_labels()
    return {"labels": labels}


@router.get("/graph/label/popular")
async def lightrag_get_popular_labels(
    limit: int = Query(default=10, ge=1, le=100),
    user=Depends(get_current_user)
):
    """Get most popular entity type labels."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    try:
        graph_storage = service.rag.chunk_entity_relation_graph
        nx_graph = await graph_storage._get_graph()
        
        label_counts = {}
        for node_id in nx_graph.nodes():
            entity_type = nx_graph.nodes[node_id].get("entity_type", "UNKNOWN")
            label_counts[entity_type] = label_counts.get(entity_type, 0) + 1
        
        sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
        return {"labels": [{"label": l, "count": c} for l, c in sorted_labels[:limit]]}
    except Exception as e:
        return {"labels": []}


@router.get("/graph/label/search")
async def lightrag_search_labels(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
    user=Depends(get_current_user)
):
    """Search entity type labels."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    labels = await service.get_graph_labels()
    q_lower = q.lower()
    matched = [l for l in labels if q_lower in l.lower()]
    return {"labels": matched[:limit]}


@router.get("/graph/entity/search")
async def lightrag_search_entities(
    q: str = Query(..., min_length=1),
    user=Depends(get_current_user)
):
    """Search entities by name or description."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    results = await service.search_entity(q)
    return {"entities": results}


@router.get("/graph/entity/exists")
async def lightrag_entity_exists(
    name: str = Query(...),
    user=Depends(get_current_user)
):
    """Check if an entity exists."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    try:
        graph_storage = service.rag.chunk_entity_relation_graph
        nx_graph = await graph_storage._get_graph()
        exists = name in nx_graph.nodes()
        return {"exists": exists, "name": name}
    except Exception:
        return {"exists": False, "name": name}


@router.post("/graph/entity/edit")
async def lightrag_edit_entity(req: EntityEditRequest, user=Depends(get_current_user)):
    """Edit entity properties."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    new_data = {}
    if req.description is not None:
        new_data["description"] = req.description
    if req.entity_type is not None:
        new_data["entity_type"] = req.entity_type
    
    result = await service.edit_entity(req.entity_name, new_data)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/graph/relation/edit")
async def lightrag_edit_relation(req: RelationEditRequest, user=Depends(get_current_user)):
    """Edit relation properties."""
    service = get_lightrag_service()
    if not service._initialized:
        await service.initialize()
    
    new_data = {}
    if req.description is not None:
        new_data["description"] = req.description
    if req.keywords is not None:
        new_data["keywords"] = req.keywords
    if req.weight is not None:
        new_data["weight"] = req.weight
    
    result = await service.edit_relation(req.source, req.target, new_data)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ==================== QUERY STRATEGIES ====================

@router.get("/strategies")
async def lightrag_get_strategies():
    """Get available query modes/strategies."""
    return {
        "strategies": [
            {
                "id": "naive",
                "name": "Naive",
                "description": "Simple vector similarity search without graph context"
            },
            {
                "id": "local",
                "name": "Local Search",
                "description": "Low-level retrieval focusing on specific entities and their relationships"
            },
            {
                "id": "global",
                "name": "Global Search",
                "description": "High-level retrieval focusing on themes and community-level understanding"
            },
            {
                "id": "hybrid",
                "name": "Hybrid Search",
                "description": "Combines local and global search for comprehensive results"
            },
            {
                "id": "mix",
                "name": "Mix Search",
                "description": "Advanced mode combining all retrieval strategies with reranking"
            },
        ]
    }
