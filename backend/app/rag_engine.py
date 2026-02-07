import faiss
import numpy as np
import pickle
import os
from typing import List, Dict
from pathlib import Path


class SharedRAGEngine:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.vector_store_path = Path(os.getenv("VECTOR_STORE_PATH", "./data/vector_store"))

        # Determine embedding dimension based on provider
        if self.embedding_provider == "sentence-transformers":
            self.embedding_dim = 384  # all-MiniLM-L6-v2
        else:
            self.embedding_dim = 768  # nomic-embed-text (ollama)

        self._st_model = None
        self.index = None
        self.documents = []
        self.metadatas = []

        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self._load_or_create_index()

    def _get_st_model(self):
        """Lazy-load sentence-transformers model."""
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.embedding_model_name)
            actual_dim = self._st_model.get_sentence_embedding_dimension()
            if actual_dim != self.embedding_dim:
                print(f"Warning: Expected {self.embedding_dim}d, got {actual_dim}d from {self.embedding_model_name}")
                self.embedding_dim = actual_dim
        return self._st_model

    def _load_or_create_index(self):
        index_file = self.vector_store_path / "faiss_index.bin"
        data_file = self.vector_store_path / "documents.pkl"

        if index_file.exists() and data_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))
                with open(data_file, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data['documents']
                    self.metadatas = data['metadatas']

                # Check if index dimension matches configured dimension
                loaded_dim = self.index.d
                if loaded_dim != self.embedding_dim:
                    print(f"Warning: Loaded index has dimension {loaded_dim}, "
                          f"configured dimension is {self.embedding_dim}. "
                          f"Using loaded dimension. Reindex if you change embedding provider.")
                    self.embedding_dim = loaded_dim

                print(f"Loaded {len(self.documents)} documents from vector store "
                      f"(dim={self.embedding_dim})")
            except Exception as e:
                print(f"Error loading index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        # For sentence-transformers, detect actual dimension
        if self.embedding_provider == "sentence-transformers":
            try:
                model = self._get_st_model()
                self.embedding_dim = model.get_sentence_embedding_dimension()
            except Exception:
                pass  # Use default

        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.documents = []
        self.metadatas = []
        print(f"Created new FAISS index (dim={self.embedding_dim}, provider={self.embedding_provider})")

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        if self.embedding_provider == "sentence-transformers":
            return self._embed_with_sentence_transformers(texts)
        else:
            return self._embed_with_ollama(texts)

    def _embed_with_sentence_transformers(self, texts: List[str]) -> np.ndarray:
        model = self._get_st_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings = embeddings.astype('float32')

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-10)

        return embeddings

    def _embed_with_ollama(self, texts: List[str]) -> np.ndarray:
        import ollama
        client = ollama.Client(host=self.ollama_host)
        embeddings = []

        for text in texts:
            response = client.embeddings(
                model=self.embedding_model_name,
                prompt=text
            )
            embeddings.append(response['embedding'])

        embeddings = np.array(embeddings, dtype='float32')

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-10)

        return embeddings

    def add_documents(self, texts: List[str], metadatas: List[Dict]) -> None:
        if not texts:
            return

        print(f"Adding {len(texts)} chunks to knowledge base...")

        embeddings = self._embed_texts(texts)
        self.index.add(embeddings)
        self.documents.extend(texts)
        self.metadatas.extend(metadatas)
        self.save()

        print(f"Total documents in knowledge base: {len(self.documents)}")

    def search(self, query: str, k: int = 5) -> Dict:
        if len(self.documents) == 0:
            return {"documents": [], "metadatas": [], "distances": []}

        query_embedding = self._embed_texts([query])
        k = min(k, len(self.documents))
        distances, indices = self.index.search(query_embedding, k)

        return {
            "documents": [self.documents[i] for i in indices[0]],
            "metadatas": [self.metadatas[i] for i in indices[0]],
            "distances": distances[0].tolist()
        }

    def query_with_context(self, question: str, k: int = 5, graph_context: str = "") -> Dict:
        search_results = self.search(question, k=k)

        context_str = ""
        if search_results["documents"]:
            context_str = "\n\n---\n\n".join(search_results["documents"])

        # Build combined prompt with optional graph context
        prompt_parts = []

        if graph_context:
            prompt_parts.append(graph_context)

        if context_str:
            prompt_parts.append(f"=== DOCUMENT INFORMATION ===\n{context_str}")

        if prompt_parts:
            combined_context = "\n\n".join(prompt_parts)
            prompt = f"""Based on the following knowledge graph relationships and document information, answer the question accurately and in detail.

{combined_context}

QUESTION: {question}

Use both the relationship data from the Knowledge Graph and the detailed content from documents to provide a comprehensive answer. If the information is not sufficient, state that clearly."""
        else:
            prompt = question

        # Use LangChain ChatOllama for consistency with LDR
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = ChatOllama(
                base_url=self.ollama_host,
                model=self.llm_model,
                temperature=0.7
            )

            messages = [
                SystemMessage(content='You are a company AI assistant with knowledge graph reasoning capabilities. Answer based on internal documents and entity relationships. Be helpful and accurate.'),
                HumanMessage(content=prompt)
            ]

            response = llm.invoke(messages)
            answer = response.content
        except Exception as e:
            print(f"LangChain LLM error, falling back to ollama client: {e}")
            import ollama
            client = ollama.Client(host=self.ollama_host)
            response = client.chat(
                model=self.llm_model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a company AI assistant with knowledge graph reasoning capabilities. Answer based on internal documents and entity relationships. Be helpful and accurate.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            answer = response['message']['content']

        return {
            "answer": answer,
            "sources": search_results["documents"][:3],
            "num_sources": len(search_results["documents"])
        }

    def save(self):
        index_file = self.vector_store_path / "faiss_index.bin"
        data_file = self.vector_store_path / "documents.pkl"

        faiss.write_index(self.index, str(index_file))
        with open(data_file, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'metadatas': self.metadatas
            }, f)

    def get_stats(self) -> Dict:
        return {
            "total_chunks": len(self.documents),
            "embedding_dimension": self.embedding_dim,
            "embedding_provider": self.embedding_provider,
            "llm_model": self.llm_model,
            "embedding_model": self.embedding_model_name
        }

    def delete_document_chunks(self, filename: str) -> int:
        """Remove all chunks belonging to a specific document and rebuild index."""
        indices_to_keep = []
        for i, meta in enumerate(self.metadatas):
            if meta.get("filename") != filename:
                indices_to_keep.append(i)

        removed_count = len(self.documents) - len(indices_to_keep)
        if removed_count == 0:
            return 0

        self.documents = [self.documents[i] for i in indices_to_keep]
        self.metadatas = [self.metadatas[i] for i in indices_to_keep]

        # Rebuild FAISS index
        self._create_new_index()
        if self.documents:
            embeddings = self._embed_texts(self.documents)
            self.index.add(embeddings)

        self.save()
        return removed_count


_rag_engine = None


def get_rag_engine() -> SharedRAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = SharedRAGEngine()
    return _rag_engine
