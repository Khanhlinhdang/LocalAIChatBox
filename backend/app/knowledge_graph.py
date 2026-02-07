import networkx as nx
import json
import re
import pickle
import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class KnowledgeGraphEngine:
    """
    Knowledge Graph engine that extracts entities and relationships from documents,
    builds a graph, and provides graph-based querying capabilities.
    """

    def __init__(self, ollama_host: str, llm_model: str, persist_path: str):
        self.ollama_host = ollama_host
        self.llm_model = llm_model
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)

        self.graph = nx.MultiDiGraph()
        self._load_graph()

    def _get_llm(self):
        """Get LangChain LLM instance with fallback."""
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=self.ollama_host,
                model=self.llm_model,
                temperature=0.1
            )
        except Exception:
            return None

    def _load_graph(self):
        graph_file = self.persist_path / "knowledge_graph.pkl"
        if graph_file.exists():
            try:
                with open(graph_file, 'rb') as f:
                    self.graph = pickle.load(f)
                print(f"Loaded knowledge graph: {self.graph.number_of_nodes()} nodes, "
                      f"{self.graph.number_of_edges()} edges")
            except Exception as e:
                print(f"Error loading knowledge graph: {e}")
                self.graph = nx.MultiDiGraph()
        else:
            print("Created new knowledge graph")

    def save(self):
        graph_file = self.persist_path / "knowledge_graph.pkl"
        with open(graph_file, 'wb') as f:
            pickle.dump(self.graph, f)

    def extract_entities_and_relations(self, text: str, doc_id: str, filename: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract entities and relationships from text using the LLM."""
        # Truncate very long texts to avoid overwhelming the LLM
        if len(text) > 3000:
            text = text[:3000]

        prompt = f"""Analyze the following text and extract entities and relationships.

Text:
{text}

Return ONLY valid JSON in this exact format, no other text:
{{
  "entities": [
    {{"name": "Entity Name", "type": "PERSON|ORGANIZATION|PROJECT|TECHNOLOGY|PRODUCT|LOCATION|CONCEPT"}}
  ],
  "relations": [
    {{"source": "Entity1", "target": "Entity2", "relation": "WORKS_FOR|CEO_OF|CREATED_BY|PART_OF|USES|INTEGRATES_WITH|RELATED_TO|MANAGES|DEPENDS_ON|LOCATED_IN"}}
  ]
}}

Rules:
- Entity names should be normalized (capitalize properly)
- Only extract clear, explicit relationships
- Keep entity names concise
- Return empty arrays if no entities/relations found"""

        try:
            result_text = ""
            llm = self._get_llm()

            if llm is not None:
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content='You are an entity and relationship extraction expert. Return ONLY valid JSON, nothing else.'),
                    HumanMessage(content=prompt)
                ]
                response = llm.invoke(messages)
                result_text = response.content
            else:
                # Fallback to direct ollama client
                import ollama
                client = ollama.Client(host=self.ollama_host)
                response = client.chat(
                    model=self.llm_model,
                    messages=[
                        {
                            'role': 'system',
                            'content': 'You are an entity and relationship extraction expert. Return ONLY valid JSON, nothing else.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    options={'temperature': 0.1}
                )
                result_text = response['message']['content']

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                entities = result.get('entities', [])
                relations = result.get('relations', [])

                # Add source document reference
                for entity in entities:
                    entity['source_doc'] = doc_id
                    entity['source_file'] = filename

                return entities, relations
            else:
                return [], []

        except Exception as e:
            print(f"Entity extraction error: {e}")
            return [], []

    def add_document_to_graph(self, doc_id: str, filename: str, chunks: List[str]):
        """Process document chunks and add extracted entities/relations to the graph."""
        all_entities = []
        all_relations = []

        # Process each chunk (limit to avoid very long processing)
        for i, chunk in enumerate(chunks[:20]):
            if len(chunk.strip()) < 50:
                continue

            entities, relations = self.extract_entities_and_relations(
                chunk, doc_id, filename
            )
            all_entities.extend(entities)
            all_relations.extend(relations)

        # Add entities to graph
        for entity in all_entities:
            name = entity['name'].strip()
            if not name:
                continue

            if self.graph.has_node(name):
                # Update existing node - add source doc reference
                node_data = self.graph.nodes[name]
                source_docs = node_data.get('source_docs', [])
                if doc_id not in source_docs:
                    source_docs.append(doc_id)
                    self.graph.nodes[name]['source_docs'] = source_docs
                source_files = node_data.get('source_files', [])
                if filename not in source_files:
                    source_files.append(filename)
                    self.graph.nodes[name]['source_files'] = source_files
            else:
                self.graph.add_node(
                    name,
                    type=entity.get('type', 'CONCEPT'),
                    source_docs=[doc_id],
                    source_files=[filename]
                )

        # Add relations to graph
        for relation in all_relations:
            source = relation.get('source', '').strip()
            target = relation.get('target', '').strip()
            rel_type = relation.get('relation', 'RELATED_TO')

            if not source or not target:
                continue

            # Ensure both nodes exist
            if not self.graph.has_node(source):
                self.graph.add_node(source, type='CONCEPT', source_docs=[doc_id], source_files=[filename])
            if not self.graph.has_node(target):
                self.graph.add_node(target, type='CONCEPT', source_docs=[doc_id], source_files=[filename])

            self.graph.add_edge(
                source, target,
                relation=rel_type,
                source_doc=doc_id,
                source_file=filename
            )

        self.save()

        return {
            "entities_added": len(all_entities),
            "relations_added": len(all_relations),
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges()
        }

    def remove_document_from_graph(self, doc_id: str):
        """Remove all entities and relations from a specific document."""
        nodes_to_remove = []
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            source_docs = node_data.get('source_docs', [])
            if doc_id in source_docs:
                source_docs.remove(doc_id)
                if not source_docs:
                    nodes_to_remove.append(node)
                else:
                    self.graph.nodes[node]['source_docs'] = source_docs

        # Remove edges from this document
        edges_to_remove = []
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if data.get('source_doc') == doc_id:
                edges_to_remove.append((u, v, key))

        for u, v, key in edges_to_remove:
            self.graph.remove_edge(u, v, key)

        # Remove orphaned nodes
        for node in nodes_to_remove:
            self.graph.remove_node(node)

        self.save()

    def find_entities(self, query: str) -> List[Dict]:
        """Find entities that match the query using fuzzy matching."""
        matched = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for node in self.graph.nodes():
            node_lower = node.lower()
            node_data = self.graph.nodes[node]
            score = 0

            # Exact substring match
            if query_lower in node_lower or node_lower in query_lower:
                score = 100

            # Word overlap
            node_words = set(node_lower.split())
            overlap = query_words & node_words
            if overlap:
                score = max(score, len(overlap) * 50)

            if score > 0:
                matched.append({
                    "name": node,
                    "type": node_data.get('type', 'UNKNOWN'),
                    "score": score,
                    "source_files": node_data.get('source_files', [])
                })

        matched.sort(key=lambda x: x['score'], reverse=True)
        return matched[:10]

    def get_entity_subgraph(self, entity: str, max_hops: int = 2) -> Dict:
        """Get subgraph around an entity within max_hops distance."""
        if entity not in self.graph:
            return {"nodes": [], "edges": [], "center": entity}

        # BFS to collect neighbors
        visited = {entity}
        current_level = {entity}

        for _ in range(max_hops):
            next_level = set()
            for node in current_level:
                for neighbor in self.graph.successors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
                for neighbor in self.graph.predecessors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level

        # Build response structure
        nodes = []
        for node in visited:
            node_data = self.graph.nodes[node]
            nodes.append({
                "id": node,
                "type": node_data.get('type', 'UNKNOWN'),
                "source_files": node_data.get('source_files', [])
            })

        edges = []
        for source, target, data in self.graph.edges(data=True):
            if source in visited and target in visited:
                edges.append({
                    "source": source,
                    "target": target,
                    "relation": data.get('relation', 'RELATED_TO'),
                    "source_file": data.get('source_file', '')
                })

        return {"nodes": nodes, "edges": edges, "center": entity}

    def get_graph_context(self, question: str) -> str:
        """Generate textual context from the knowledge graph for a question."""
        entities = self.find_entities(question)
        if not entities:
            return ""

        context_parts = []
        seen_edges = set()

        for entity_info in entities[:5]:
            entity = entity_info['name']
            subgraph = self.get_entity_subgraph(entity, max_hops=2)

            if not subgraph['edges']:
                continue

            part = f"\n[Entity: {entity} ({entity_info['type']})]"
            for edge in subgraph['edges']:
                edge_key = (edge['source'], edge['relation'], edge['target'])
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    part += f"\n  - {edge['source']} --[{edge['relation']}]--> {edge['target']}"

            context_parts.append(part)

        if not context_parts:
            return ""

        return "=== KNOWLEDGE GRAPH RELATIONSHIPS ===\n" + "\n".join(context_parts)

    def get_all_entities(self) -> List[Dict]:
        """Get all entities in the knowledge graph."""
        entities = []
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            degree = self.graph.degree(node)
            entities.append({
                "name": node,
                "type": node_data.get('type', 'UNKNOWN'),
                "connections": degree,
                "source_files": node_data.get('source_files', [])
            })

        entities.sort(key=lambda x: x['connections'], reverse=True)
        return entities

    def get_stats(self) -> Dict:
        """Get knowledge graph statistics."""
        type_counts = {}
        for node in self.graph.nodes():
            node_type = self.graph.nodes[node].get('type', 'UNKNOWN')
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        relation_counts = {}
        for _, _, data in self.graph.edges(data=True):
            rel = data.get('relation', 'UNKNOWN')
            relation_counts[rel] = relation_counts.get(rel, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "entity_types": type_counts,
            "relation_types": relation_counts
        }

    def clear(self):
        """Clear the entire knowledge graph."""
        self.graph = nx.MultiDiGraph()
        self.save()


# Singleton
_kg_engine: Optional[KnowledgeGraphEngine] = None


def get_kg_engine() -> KnowledgeGraphEngine:
    global _kg_engine
    if _kg_engine is None:
        _kg_engine = KnowledgeGraphEngine(
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            llm_model=os.getenv("OLLAMA_LLM_MODEL", "llama3.1"),
            persist_path=os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
        )
    return _kg_engine
