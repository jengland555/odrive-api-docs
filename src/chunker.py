"""
Heading-Based Semantic Chunker (H2/H3 Slicing Engine)
Ports the Technical Writer's Semantic Chunking Architecture from Stripe AI Assistant to Python.
Chunks markdown documents at logical conceptual boundaries (H2/H3) rather than arbitrary character counts.
"""

import os
import re
import json
import math
from typing import Dict, Any, List
from .frontmatter_checker import FrontmatterValidator

class SemanticChunker:
    def __init__(self, rules_config: Dict[str, Any] = None):
        self.frontmatter_validator = FrontmatterValidator(rules_config or {})

    @staticmethod
    def slugify(text: str) -> str:
        """
        Creates clean URL anchor slug matching GitHub markdown renderer.
        """
        clean = re.sub(r"[^\w\s-]", "", text.lower()).strip()
        return re.sub(r"\s+", "-", clean)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimates token count (~4 characters per token for English technical prose).
        """
        words = len(text.split())
        chars = len(text)
        return max(words, math.ceil(chars / 4.0))

    def chunk_markdown_file(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Parses a single Markdown document and produces H2/H3 semantic chunks with metadata.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        metadata, markdown, _ = self.frontmatter_validator.parse_frontmatter(content)

        doc_title = metadata.get("title", filename.replace(".md", "").replace("_", " ").title())
        category = metadata.get("category", "General")
        firmware_version = metadata.get("firmware_version", "latest")
        tags = metadata.get("tags", [])
        base_slug = metadata.get("slug", filename.replace(".md", ""))

        lines = markdown.split("\n")
        chunks = []

        current_heading = doc_title
        current_heading_level = 1
        current_slug_anchor = ""
        current_buffer = []

        def save_chunk():
            text = "\n".join(current_buffer).strip()
            # Retain non-empty chunks with meaningful content
            if len(text) > 40:
                chunk_index = len(chunks) + 1
                chunk_id = f"{filename.replace('.md', '')}_chunk_{chunk_index:02d}"
                anchor_suffix = f"#{current_slug_anchor}" if current_slug_anchor else ""
                url = f"{base_slug}{anchor_suffix}"

                chunks.append({
                    "chunk_id": chunk_id,
                    "doc_title": doc_title,
                    "filename": filename,
                    "section": current_heading,
                    "heading_level": current_heading_level,
                    "anchor_slug": current_slug_anchor,
                    "url": url,
                    "category": category,
                    "firmware_version": firmware_version,
                    "tags": tags,
                    "estimated_tokens": self.estimate_tokens(text),
                    "character_count": len(text),
                    "text": text
                })
            current_buffer.clear()

        for line in lines:
            # Detect H2 or H3 markdown headers (## or ###)
            heading_match = re.match(r"^(#{2,3})\s+(.*)$", line.strip())
            if heading_match:
                save_chunk()
                current_heading_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                current_slug_anchor = self.slugify(current_heading)
                current_buffer.append(line)
            else:
                current_buffer.append(line)

        # Save the trailing chunk
        save_chunk()

        return chunks

    def build_chunk_index(self, docs_dir: str, output_path: str = "data/rag_semantic_chunks.json") -> Dict[str, Any]:
        """
        Scans docs directory, extracts semantic chunks for all documents, and writes JSON index.
        """
        if not os.path.exists(docs_dir):
            raise FileNotFoundError(f"Documentation directory '{docs_dir}' not found.")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        md_files = [
            os.path.join(docs_dir, f)
            for f in sorted(os.listdir(docs_dir))
            if f.endswith(".md") or f.endswith(".mdx")
        ]

        all_chunks = []
        for file_path in md_files:
            file_chunks = self.chunk_markdown_file(file_path)
            all_chunks.extend(file_chunks)

        total_tokens = sum(c["estimated_tokens"] for c in all_chunks)
        avg_tokens = round(total_tokens / max(len(all_chunks), 1), 1)

        payload = {
            "index_version": "1.0.0",
            "chunking_strategy": "H2/H3 Heading-Based Semantic Boundaries",
            "source_directory": docs_dir,
            "total_documents": len(md_files),
            "total_chunks": len(all_chunks),
            "total_estimated_tokens": total_tokens,
            "avg_tokens_per_chunk": avg_tokens,
            "chunks": all_chunks
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return payload
