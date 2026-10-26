"""Extracción de texto desde archivos .txt y .pdf."""

from __future__ import annotations

from pathlib import Path


def extract_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo: {path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _read_txt(path)
    if suffix in {".md", ".markdown"}:
        return _read_txt(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    raise ValueError("Formato no compatible. Usa .txt, .md, .docx o .pdf")


def _read_txt(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "Falta pypdf. Instálalo con: pip install -r requirements.txt"
        ) from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            parts.append(text)
    if not parts:
        raise ValueError(
            "No se pudo extraer texto del PDF. "
            "Puede ser un escaneo (imagen). Pega el texto manualmente."
        )
    return "\n\n".join(parts)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "Falta python-docx. Instálalo con: pip install -r requirements.txt"
        ) from exc

    document = Document(str(path))
    blocks: list[str] = []
    # Mantiene el orden de los párrafos y tablas del documento.
    for block in document.iter_inner_content():
        if hasattr(block, "rows"):
            for row in block.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    blocks.append(" | ".join(cells))
        else:
            paragraph = block.text.strip()
            if paragraph:
                blocks.append(paragraph)

    text = "\n\n".join(blocks)
    if not text:
        raise ValueError("El documento Word no contiene texto que se pueda extraer.")
    return text
