"""
Export Service for LocalAIChatBox.
Exports chat history, research reports, knowledge graph data,
and analytics as JSON, CSV, or Markdown.

Inspired by LightRAG's structured data export and RAG-Anything's
batch processing output patterns.
"""

import csv
import io
import json
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import Conversation, ChatSession, ResearchTask, Document, UsageLog, User


def export_chat_history(db: Session, user_id: int, session_id: str = None,
                        format: str = "json") -> Dict:
    """Export chat history as JSON, CSV, or Markdown."""
    query = db.query(Conversation).filter(Conversation.user_id == user_id)
    if session_id:
        query = query.filter(Conversation.session_id == session_id)
    conversations = query.order_by(Conversation.created_at.asc()).all()

    if format == "json":
        data = []
        for conv in conversations:
            data.append({
                "id": conv.id,
                "question": conv.question,
                "answer": conv.answer,
                "sources_used": conv.sources_used,
                "search_mode": conv.search_mode or "hybrid",
                "created_at": conv.created_at.isoformat(),
                "session_id": conv.session_id,
            })
        return {
            "content": json.dumps(data, indent=2, ensure_ascii=False),
            "filename": f"chat_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            "content_type": "application/json",
        }

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Question", "Answer", "Sources", "Search Mode", "Created At"])
        for conv in conversations:
            writer.writerow([
                conv.id, conv.question, conv.answer,
                conv.sources_used, conv.search_mode or "hybrid",
                conv.created_at.isoformat(),
            ])
        return {
            "content": output.getvalue(),
            "filename": f"chat_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv",
        }

    elif format == "markdown":
        md = f"# Chat History Export\n\n"
        md += f"**User ID**: {user_id}\n"
        md += f"**Exported at**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        md += f"**Total messages**: {len(conversations)}\n\n---\n\n"

        for conv in conversations:
            md += f"### Q: {conv.question}\n\n"
            md += f"{conv.answer}\n\n"
            if conv.sources_used:
                md += f"*Sources: {conv.sources_used}*\n\n"
            md += f"*{conv.created_at.strftime('%Y-%m-%d %H:%M')}*\n\n---\n\n"

        return {
            "content": md,
            "filename": f"chat_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md",
            "content_type": "text/markdown",
        }

    raise ValueError(f"Unsupported format: {format}")


def export_research_report(db: Session, task_id: str, user_id: int,
                           format: str = "markdown") -> Dict:
    """Export a research report."""
    task = db.query(ResearchTask).filter(
        ResearchTask.id == task_id,
        ResearchTask.user_id == user_id,
    ).first()

    if not task:
        return None

    if format == "markdown":
        md = f"# Research Report\n\n"
        md += f"**Query**: {task.query}\n\n"
        md += f"**Strategy**: {task.strategy}\n\n"
        md += f"**Status**: {task.status}\n\n"
        md += f"**Created**: {task.created_at.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        if task.completed_at:
            md += f"**Completed**: {task.completed_at.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        md += f"---\n\n"

        if task.result_knowledge:
            md += f"## Findings\n\n{task.result_knowledge}\n\n"

        if task.result_report:
            md += f"## Detailed Report\n\n{task.result_report}\n\n"

        if task.result_sources:
            md += f"## Sources\n\n"
            try:
                sources = json.loads(task.result_sources)
                for i, src in enumerate(sources, 1):
                    if isinstance(src, dict):
                        md += f"{i}. **{src.get('title', 'Source')}**\n"
                        if src.get('url'):
                            md += f"   URL: {src['url']}\n"
                        if src.get('snippet'):
                            md += f"   {src['snippet']}\n"
                    else:
                        md += f"{i}. {src}\n"
                    md += "\n"
            except (json.JSONDecodeError, TypeError):
                md += f"{task.result_sources}\n\n"

        return {
            "content": md,
            "filename": f"research_{task_id[:8]}_{datetime.utcnow().strftime('%Y%m%d')}.md",
            "content_type": "text/markdown",
        }

    elif format == "json":
        data = {
            "id": task.id,
            "query": task.query,
            "strategy": task.strategy,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "findings": task.result_knowledge,
            "report": task.result_report,
            "sources": json.loads(task.result_sources) if task.result_sources else [],
            "metadata": json.loads(task.result_metadata) if task.result_metadata else {},
        }
        return {
            "content": json.dumps(data, indent=2, ensure_ascii=False),
            "filename": f"research_{task_id[:8]}_{datetime.utcnow().strftime('%Y%m%d')}.json",
            "content_type": "application/json",
        }

    raise ValueError(f"Unsupported format: {format}")


def export_knowledge_graph(kg_engine, format: str = "json") -> Dict:
    """Export knowledge graph data."""
    all_entities = kg_engine.get_all_entities()
    stats = kg_engine.get_stats()

    # Get all edges
    edges = []
    for u, v, data in kg_engine.graph.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "relation": data.get("relation", "RELATED_TO"),
            "source_doc": data.get("source_doc", ""),
            "source_file": data.get("source_file", ""),
        })

    if format == "json":
        data = {
            "stats": stats,
            "entities": all_entities,
            "edges": edges,
            "exported_at": datetime.utcnow().isoformat(),
        }
        return {
            "content": json.dumps(data, indent=2, ensure_ascii=False),
            "filename": f"knowledge_graph_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            "content_type": "application/json",
        }

    elif format == "csv":
        # Export nodes CSV
        nodes_output = io.StringIO()
        writer = csv.writer(nodes_output)
        writer.writerow(["Name", "Type", "Connections", "Source Files"])
        for entity in all_entities:
            writer.writerow([
                entity.get("name", ""),
                entity.get("type", "CONCEPT"),
                entity.get("connections", 0),
                "; ".join(entity.get("source_files", [])),
            ])

        # Export edges CSV
        edges_output = io.StringIO()
        writer2 = csv.writer(edges_output)
        writer2.writerow(["Source", "Target", "Relation", "Source File"])
        for edge in edges:
            writer2.writerow([
                edge["source"], edge["target"],
                edge["relation"], edge.get("source_file", ""),
            ])

        combined = f"=== ENTITIES ===\n{nodes_output.getvalue()}\n\n=== RELATIONSHIPS ===\n{edges_output.getvalue()}"
        return {
            "content": combined,
            "filename": f"knowledge_graph_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv",
        }

    elif format == "graphml":
        # Export as GraphML for use in external graph tools
        import networkx as nx
        output = io.BytesIO()
        nx.write_graphml(kg_engine.graph, output)
        return {
            "content": output.getvalue().decode("utf-8"),
            "filename": f"knowledge_graph_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.graphml",
            "content_type": "application/xml",
        }

    raise ValueError(f"Unsupported format: {format}")


def export_documents_list(db: Session, format: str = "csv") -> Dict:
    """Export document list with metadata."""
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Filename", "Type", "Size (MB)", "Chunks",
                         "Uploaded By", "Uploaded At", "Indexed", "Folder ID", "Version"])
        for doc in documents:
            writer.writerow([
                doc.id, doc.filename, doc.file_type, doc.file_size_mb,
                doc.num_chunks, doc.uploader.username if doc.uploader else "Unknown",
                doc.uploaded_at.isoformat(), doc.is_indexed,
                doc.folder_id, doc.version,
            ])
        return {
            "content": output.getvalue(),
            "filename": f"documents_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv",
        }

    elif format == "json":
        data = []
        for doc in documents:
            data.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size_mb": doc.file_size_mb,
                "num_chunks": doc.num_chunks,
                "uploaded_by": doc.uploader.username if doc.uploader else "Unknown",
                "uploaded_at": doc.uploaded_at.isoformat(),
                "is_indexed": doc.is_indexed,
                "folder_id": doc.folder_id,
                "version": doc.version,
                "description": doc.description,
            })
        return {
            "content": json.dumps(data, indent=2, ensure_ascii=False),
            "filename": f"documents_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            "content_type": "application/json",
        }

    raise ValueError(f"Unsupported format: {format}")
