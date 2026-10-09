"""Resumen ordenado de manuales: API opcional + fallback heurístico."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .corrector import correct_text

SECTIONS = (
    ("Identificación", ("marca", "modelo", "capacidad", "kg", "tipo", "dimensiones", "peso", "referencia", "serie")),
    ("Conexión", ("conexión", "conectar", "agua", "desagüe", "desague", "electric", "voltaje", "enchufe", "toma", "manguera", "instalación", "instalacion")),
    ("Programas", ("programa", "ciclo", "algodón", "algodon", "sintético", "sintetico", "delicado", "rápido", "rapido", "centrifug", "temperatura", "rpm", "duración", "duracion")),
    ("Uso diario", ("uso", "cargar", "carga", "detergente", "suavizante", "bloquear", "bloqueo", "puerta", "tambor", "inicio", "pausa", "panel")),
    ("Mantenimiento", ("mantenimiento", "limpiar", "limpieza", "filtro", "junta", "cubeta", "cajetín", "cajetin", "descalcif", "cuidado")),
    ("Averías", ("error", "avería", "averia", "código", "codigo", "falla", "problema", "alarma", "e0", "e1", "e2", "e3", "e4", "solución", "solucion")),
    ("Advertencias", ("advertencia", "peligro", "riesgo", "precaución", "precaucion", "no tocar", "prohibido", "importante", "atención", "atencion", "seguridad")),
)

SECTION_ORDER = [name for name, _ in SECTIONS]

SYSTEM_PROMPT = """Eres un asistente que convierte manuales técnicos largos en fichas cortas y claras en español.
Extrae solo datos útiles y ordénalos exactamente en estas secciones (omite una sección si no hay datos):

## Identificación
## Conexión
## Programas
## Uso diario
## Mantenimiento
## Averías
## Advertencias

Reglas:
- Español correcto y conciso.
- Viñetas cortas (una idea por línea).
- No inventes datos que no estén en el texto.
- Si un dato no aparece, no lo rellenes.
"""


@dataclass
class SummaryResult:
    text: str
    engine: str  # "api" | "local"


def summarize_manual(text: str, *, use_api: bool = True) -> SummaryResult:
    cleaned = (text or "").strip()
    if not cleaned:
        return SummaryResult("No hay texto para resumir.", "local")

    if use_api:
        api_result = _try_api_summary(cleaned)
        if api_result is not None:
            return SummaryResult(correct_text(api_result), "api")

    return SummaryResult(correct_text(_local_summary(cleaned)), "local")


def _chunk_text(text: str, max_chars: int = 12000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split = text.rfind("\n", start, end)
            if split > start + max_chars // 2:
                end = split
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def _try_api_summary(text: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = os.getenv("FICHAMANUAL_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    client = OpenAI(api_key=api_key)
    chunks = _chunk_text(text)
    partials: list[str] = []

    try:
        for i, chunk in enumerate(chunks, start=1):
            user = (
                f"Parte {i}/{len(chunks)} del manual. "
                "Extrae los datos importantes en formato de ficha:\n\n"
                f"{chunk}"
            )
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                partials.append(content)

        if not partials:
            return None
        if len(partials) == 1:
            return partials[0]

        merge_prompt = (
            "Combina estas fichas parciales en UNA sola ficha final, "
            "sin duplicar datos, usando las mismas secciones:\n\n"
            + "\n\n---\n\n".join(partials)
        )
        merged = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": merge_prompt},
            ],
        )
        return (merged.choices[0].message.content or "").strip() or None
    except Exception:
        return None


def _local_summary(text: str) -> str:
    lines = _normalize_lines(text)
    buckets: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    seen: set[str] = set()

    for line in lines:
        section = _classify_line(line)
        if section is None:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        if len(buckets[section]) < 12:
            buckets[section].append(f"- {line}")

    # Si hay poco contenido clasificado, añade frases densas a Identificación/Uso
    classified = sum(len(v) for v in buckets.values())
    if classified < 6:
        dense = _dense_sentences(text, limit=10)
        for sentence in dense:
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            buckets["Identificación"].append(f"- {sentence}")

    parts: list[str] = ["# Ficha del manual", ""]
    for name in SECTION_ORDER:
        items = buckets[name]
        if not items:
            continue
        parts.append(f"## {name}")
        parts.extend(items)
        parts.append("")

    if len(parts) <= 2:
        preview = text.strip().replace("\n", " ")
        preview = re.sub(r"\s+", " ", preview)[:500]
        parts.append("## Resumen aproximado")
        parts.append(f"- {preview}...")
        parts.append("")
        parts.append(
            "_Modo local: no se detectaron secciones claras. "
            "Para mejores resultados, configura OPENAI_API_KEY._"
        )

    parts.append(f"_Motor: local (heurístico). Caracteres leídos: {len(text)}._")
    return "\n".join(parts).strip()


def _normalize_lines(text: str) -> list[str]:
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in raw.split("\n"):
        cleaned = re.sub(r"\s+", " ", line).strip(" •*-–—\t ")
        if len(cleaned) < 12:
            continue
        if re.fullmatch(r"[\d.\-/]+", cleaned):
            continue
        if len(cleaned) > 280:
            cleaned = cleaned[:277] + "..."
        lines.append(cleaned)
    return lines


def _classify_line(line: str) -> str | None:
    lower = line.lower()
    best_name: str | None = None
    best_score = 0
    for name, keywords in SECTIONS:
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name if best_score > 0 else None


def _dense_sentences(text: str, limit: int = 10) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored: list[tuple[int, str]] = []
    useful = (
        "kg", "volt", "agua", "programa", "error", "filtro", "detergente",
        "temperatura", "capacidad", "modelo", "marca", "no ", "evitar",
    )
    for sentence in sentences:
        s = re.sub(r"\s+", " ", sentence).strip()
        if len(s) < 40 or len(s) > 220:
            continue
        score = sum(1 for w in useful if w in s.lower())
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return [s for _, s in scored[:limit]]
