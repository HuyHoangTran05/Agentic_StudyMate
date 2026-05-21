"""
Agentic StudyMate — Document Text Extractor

Extracts text from uploaded documents with metadata preservation.
Supports: PDF (via PyMuPDF/pymupdf4llm), DOCX (via python-docx), TXT.

Key design: Extract as Markdown to preserve structure (headings, lists, tables)
which helps the chunker make intelligent splits.
"""

import asyncio
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ExtractedPage:
    """A single page/section of extracted text."""
    page_number: int
    content: str
    headings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of document extraction."""
    pages: list[ExtractedPage]
    total_text: str
    metadata: dict = field(default_factory=dict)


async def extract_pdf(file_path: str) -> ExtractionResult:
    """
    Extract text from PDF using pymupdf4llm (Markdown output).
    
    pymupdf4llm preserves headings, tables, and lists as Markdown,
    giving the chunker structural boundaries to work with.
    """
    def _extract():
        import pymupdf4llm
        import pymupdf

        # Get page-by-page markdown
        doc = pymupdf.open(file_path)
        pages = []

        for page_num in range(len(doc)):
            # Extract markdown for this page
            md_text = pymupdf4llm.to_markdown(
                file_path,
                pages=[page_num],
                show_progress=False,
            )

            # Extract headings from the markdown
            headings = []
            for line in md_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    # Remove # prefix and clean
                    heading = stripped.lstrip("#").strip()
                    if heading:
                        headings.append(heading)

            pages.append(ExtractedPage(
                page_number=page_num + 1,  # 1-indexed
                content=md_text.strip(),
                headings=headings,
            ))

        doc.close()

        total_text = "\n\n".join(p.content for p in pages if p.content)
        return ExtractionResult(
            pages=pages,
            total_text=total_text,
            metadata={"file_type": "pdf", "total_pages": len(pages)},
        )

    # Run in thread to avoid blocking the event loop
    return await asyncio.to_thread(_extract)


async def extract_docx(file_path: str) -> ExtractionResult:
    """
    Extract text from DOCX with heading structure detection.
    
    Iterates paragraphs and detects heading styles to preserve
    document structure for intelligent chunking.
    """
    def _extract():
        from docx import Document

        doc = Document(file_path)
        pages = []
        current_content = []
        current_headings = []
        page_num = 1

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                current_content.append("")
                continue

            style_name = para.style.name.lower() if para.style else ""

            # Detect headings
            if "heading" in style_name or "title" in style_name:
                # If we have accumulated content, save as a page
                if current_content and any(line.strip() for line in current_content):
                    pages.append(ExtractedPage(
                        page_number=page_num,
                        content="\n".join(current_content).strip(),
                        headings=current_headings.copy(),
                    ))
                    page_num += 1
                    current_content = []
                    current_headings = []

                # Determine heading level
                level = 1
                if "heading 1" in style_name:
                    level = 1
                elif "heading 2" in style_name:
                    level = 2
                elif "heading 3" in style_name:
                    level = 3

                md_heading = f"{'#' * level} {text}"
                current_content.append(md_heading)
                current_headings.append(text)
            else:
                current_content.append(text)

        # Don't forget the last section
        if current_content and any(line.strip() for line in current_content):
            pages.append(ExtractedPage(
                page_number=page_num,
                content="\n".join(current_content).strip(),
                headings=current_headings.copy(),
            ))

        total_text = "\n\n".join(p.content for p in pages if p.content)
        return ExtractionResult(
            pages=pages,
            total_text=total_text,
            metadata={"file_type": "docx", "total_pages": len(pages)},
        )

    return await asyncio.to_thread(_extract)


async def extract_txt(file_path: str) -> ExtractionResult:
    """
    Extract text from a plain text file.
    
    Attempts multiple encodings for robustness.
    Splits into logical sections by double newlines.
    """
    def _extract():
        path = Path(file_path)

        # Try multiple encodings
        content = None
        for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                content = path.read_text(encoding=encoding)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is None:
            raise ValueError(f"Could not decode file: {file_path}")

        # Split into sections by double newlines
        sections = [s.strip() for s in content.split("\n\n") if s.strip()]

        pages = []
        for i, section in enumerate(sections):
            pages.append(ExtractedPage(
                page_number=i + 1,
                content=section,
                headings=[],
            ))

        return ExtractionResult(
            pages=pages,
            total_text=content,
            metadata={"file_type": "txt", "total_pages": len(pages)},
        )

    return await asyncio.to_thread(_extract)


# ─── Main Extractor Entry Point ──────────────────────────────────────────────

EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
}


async def extract_document(file_path: str, file_type: str) -> ExtractionResult:
    """
    Extract text from a document based on its file type.
    
    Args:
        file_path: Path to the uploaded file
        file_type: One of 'pdf', 'docx', 'txt'
        
    Returns:
        ExtractionResult with pages, total text, and metadata
        
    Raises:
        ValueError: If file type is not supported
    """
    extractor = EXTRACTORS.get(file_type.lower())
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}. Supported: {list(EXTRACTORS.keys())}")

    return await extractor(file_path)
