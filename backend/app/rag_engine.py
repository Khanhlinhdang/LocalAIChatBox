import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict
from pathlib import Path
import hashlib


class SharedRAGEngine:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.vector_store_path = Path(os.getenv("VECTOR_STORE_PATH", "./data/vector_store"))

        self._st_model = None
        
        # Create vector store directory
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.vector_store_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(name="documents")
            print(f"Loaded existing collection with {self.collection.count()} documents")
        except:
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            print("Created new ChromaDB collection")

    def _get_st_model(self):
        """Lazy-load sentence-transformers model."""
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.embedding_model_name)
        return self._st_model

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        if self.embedding_provider == "sentence-transformers":
            return self._embed_with_sentence_transformers(texts)
        else:
            return self._embed_with_ollama(texts)

    def _embed_with_sentence_transformers(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using sentence-transformers"""
        model = self._get_st_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # Convert to list for ChromaDB
        return embeddings.tolist()

    def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama"""
        import requests
        
        all_embeddings = []
        for text in texts:
            try:
                response = requests.post(
                    f"{self.ollama_host}/api/embeddings",
                    json={
                        "model": self.embedding_model_name,
                        "prompt": text
                    },
                    timeout=30
                )
                response.raise_for_status()
                embedding = response.json()["embedding"]
                all_embeddings.append(embedding)
            except Exception as e:
                print(f"Error getting embedding from Ollama: {e}")
                # Return zero vector as fallback
                all_embeddings.append([0.0] * 768)
        
        return all_embeddings

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict],
        doc_id: str = None
    ) -> Dict:
        """Add documents to ChromaDB collection"""
        try:
            if not texts:
                return {
                    "status": "error",
                    "message": "No texts provided"
                }
            
            # Generate embeddings
            embeddings = self._embed_texts(texts)
            
            # Generate unique IDs for each chunk
            ids = []
            for i, text in enumerate(texts):
                # Create unique ID based on doc_id and chunk index
                chunk_id = f"{doc_id}_chunk_{i}" if doc_id else f"chunk_{hashlib.md5(text.encode()).hexdigest()}"
                ids.append(chunk_id)
            
            # Add to ChromaDB
            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            
            return {
                "status": "success",
                "num_chunks": len(texts),
                "collection_size": self.collection.count()
            }
            
        except Exception as e:
            print(f"Error adding documents: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Dict = None
    ) -> List[Dict]:
        """Search for similar documents"""
        try:
            # Generate query embedding
            query_embedding = self._embed_texts([query])[0]
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, self.collection.count()),
                where=filter_metadata if filter_metadata else None
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        "text": doc,
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0.0,
                        "id": results['ids'][0][i] if results['ids'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error searching: {e}")
            return []

    def delete_by_metadata(self, filter_metadata: Dict) -> bool:
        """Delete documents by metadata filter"""
        try:
            self.collection.delete(where=filter_metadata)
            return True
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model_name
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                "total_documents": 0,
                "error": str(e)
            }

    def clear_all(self) -> bool:
        """Clear all documents from collection"""
        try:
            # Delete collection and recreate
            self.client.delete_collection(name="documents")
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            print("Cleared all documents from ChromaDB")
            return True
        except Exception as e:
            print(f"Error clearing collection: {e}")
            return False


# Singleton instance
_rag_engine = None


def get_rag_engine() -> SharedRAGEngine:
    """Get or create the singleton RAG engine instance"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = SharedRAGEngine()
    return _rag_engine
