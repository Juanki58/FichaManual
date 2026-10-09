"""Corrección básica del texto de salida."""

from __future__ import annotations

import re


_REPLACEMENTS = (
    (r"[ \t]+\n", "\n"),
    (r"\n{3,}", "\n\n"),
    (r"[ \t]{2,}", " "),
    (r"\s+([,.;:!?])", r"\1"),
    (r"([¿¡])\s+", r"\1"),
)

_WORD_FIXES = {
    "lavadoraa": "lavadora",
    "programaa": "programa",
    "detergentee": "detergente",
    "mantenimientto": "mantenimiento",
    "conectión": "conexión",
    "advertenciaa": "advertencia",
}


def correct_text(text: str) -> str:
    """Limpia espacios, saltos y erratas frecuentes simples."""
    if not text:
        return ""

    result = text.replace("\r\n", "\n").replace("\r", "\n")
    result = result.strip()

    for pattern, repl in _REPLACEMENTS:
        result = re.sub(pattern, repl, result)

    def fix_word(match: re.Match[str]) -> str:
        word = match.group(0)
        key = word.lower()
        fixed = _WORD_FIXES.get(key)
        if not fixed:
            return word
        if word.isupper():
            return fixed.upper()
        if word[0].isupper():
            return fixed.capitalize()
        return fixed

    result = re.sub(r"\b\w+\b", fix_word, result, flags=re.UNICODE)

    # Capitaliza tras punto si la siguiente letra es minúscula
    def cap_sentence(match: re.Match[str]) -> str:
        return match.group(1) + match.group(2).upper()

    result = re.sub(r"([.!?]\s+)([a-záéíóúñü])", cap_sentence, result)
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result.strip()
