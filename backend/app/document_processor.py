import os
import fitz  # PyMuPDF
from docx import Document
from typing import List, Dict


class DocumentProcessor:
    def __init__(self):
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt', '.md']

    def process_file(self, file_path: str) -> Dict:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            text = self._process_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            text = self._process_word(file_path)
        elif ext in ['.txt', '.md']:
            text = self._process_txt(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

        chunks = self.chunk_text(text)

        return {
            "text": text,
            "chunks": chunks,
            "text_length": len(text),
            "num_chunks": len(chunks)
        }

    def _process_pdf(self, file_path: str) -> str:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text

    def _process_word(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    def _process_txt(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def chunk_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            if end < len(text):
                for delim in ['. ', '.\n', '! ', '?\n', '\n\n']:
                    last_delim = text[start:end].rfind(delim)
                    if last_delim != -1:
                        end = start + last_delim + len(delim)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start += (self.chunk_size - self.chunk_overlap)

        return chunks
