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
    if suffix == ".pdf":
        return _read_pdf(path)
    raise ValueError("Formato no soportado. Usa .txt o .pdf")


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
