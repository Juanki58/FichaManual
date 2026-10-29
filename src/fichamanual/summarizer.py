"""Resumen ordenado de textos y manuales: API opcional + motor local estructurado.

Por defecto genera una ficha profesional genérica. La ficha de producto /
electrodoméstico solo se usa cuando el texto es claramente un manual de aparato.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .corrector import correct_text

MISSING = "No indicado en el texto"

# Umbral alto: en duda → siempre ficha genérica.
_PRODUCT_CONFIDENCE_THRESHOLD = 4.0

# Niveles de longitud de la ficha (GUI: Corto / Medio / Detallado).
LENGTH_SHORT = "short"
LENGTH_MEDIUM = "medium"
LENGTH_LONG = "long"
LENGTH_ALIASES = {
    "short": LENGTH_SHORT,
    "corto": LENGTH_SHORT,
    "medium": LENGTH_MEDIUM,
    "medio": LENGTH_MEDIUM,
    "long": LENGTH_LONG,
    "detallado": LENGTH_LONG,
    "detailed": LENGTH_LONG,
    "largo": LENGTH_LONG,
}

# Cupos por longitud (ficha genérica). short ≈ 3–5 hits totales.
_LENGTH_CAPS: dict[str, dict[str, int]] = {
    LENGTH_SHORT: {
        "exec_min": 3,
        "exec_max": 5,
        "ideas_max": 0,
        "facts_max": 0,
        "decisions_max": 0,
        "actions_max": 0,
        "risks_max": 0,
        "structure_max": 0,
        "conclusions_max": 0,
        "product_bullets": 3,
        "product_programs": 4,
    },
    LENGTH_MEDIUM: {
        "exec_min": 3,
        "exec_max": 4,
        "ideas_max": 5,
        "facts_max": 5,
        "decisions_max": 3,
        "actions_max": 4,
        "risks_max": 3,
        "structure_max": 5,
        "conclusions_max": 3,
        "product_bullets": 6,
        "product_programs": 10,
    },
    LENGTH_LONG: {
        "exec_min": 4,
        "exec_max": 6,
        "ideas_max": 8,
        "facts_max": 8,
        "decisions_max": 5,
        "actions_max": 6,
        "risks_max": 4,
        "structure_max": 8,
        "conclusions_max": 5,
        "product_bullets": 10,
        "product_programs": 16,
    },
}


def normalize_length(length: str | None) -> str:
    """Normaliza a short|medium|long; por defecto medium."""
    key = (length or LENGTH_MEDIUM).strip().lower()
    return LENGTH_ALIASES.get(key, LENGTH_MEDIUM)


def _length_caps(length: str | None) -> dict[str, int]:
    return _LENGTH_CAPS[normalize_length(length)]


SECTION_ORDER_PRODUCT = (
    "Identificación",
    "Especificaciones",
    "Conexión / instalación",
    "Programas",
    "Uso diario",
    "Mantenimiento",
    "Códigos de error / averías",
    "Advertencias importantes",
)

SECTION_ORDER_GENERIC = (
    "Resumen",
    "Ideas / conceptos clave",
    "Datos, cifras, fechas o definiciones",
    "Decisiones",
    "Acciones propuestas o pendientes",
    "Riesgos y dudas",
    "Estructura / apartados",
    "Conclusiones o implicaciones",
)

_SYSTEM_PROMPT_GENERIC_CORE = """Eres un asistente que confecciona una SÍNTESIS analítica en español.
Reagrupa el texto en pocos bloques temáticos densos. NO copies párrafos ni una frase por oración.
Extrae solo hechos que están en el texto. PROHIBIDO inventar cifras, porcentajes, leyes, nombres de planes o estadísticas que el texto no diga.

Formato visual (texto plano, SIN Markdown, sin #, sin ** y sin viñetas «- »):
1) Primera línea: un título corto SINTETIZADO del paradigma o tema. No copies el primer encabezado de sección ni una frase larga del cuerpo.
2) Unos pocos bloques numerados (en medio, cerca de 4), cada uno con un nombre corto:
1. Nombre breve
Etiqueta: hecho comprimido en una sola línea
Otra etiqueta: otro hecho
3) Si el propio texto contrapone dos polos (siglo XX / siglo XXI, contracción / en contraposición, un sector frente a otro), ábrelos como subbloques cortos terminados en dos puntos. Si no hay contraste explícito, no lo inventes (no añadas Occidente/Sur, norte/sur ni bandos que el texto no nombre).
4) Cierra, salvo en longitud corta, con:
Matriz Resumen de Indicadores
Dimensión | Factor clave | Indicador de control
Una fila por bloque. El indicador es un hecho concreto del texto (mecanismo, actor, política, mineral, cifra SI aparece). Si no hay números, no inventes ninguno.

Otras reglas:
- PROHIBIDO el adorno «──» y la sección «Título / tema». El título es la primera línea, sola, sin viñeta y sin etiqueta.
- El nombre de cada bloque va solo en su línea (por ejemplo «1. Inversión y capital» o «Resumen»), sin rayas a los lados.
- Cada línea «Etiqueta: hecho» es densa: nombra el mecanismo y comprime el hecho. Nada de relleno.
- Elimina LaTeX, citas [n], «Véase también», referencias y ruido de Wikipedia.
- No uses campos de electrodoméstico (Marca, Modelo, Capacidad, rpm, Programas).
- No trates un límite teórico o un concepto académico como riesgo operativo.
"""

_LENGTH_PROMPT_GENERIC = {
    LENGTH_SHORT: """Nivel de longitud: CORTO.
- Título + 2 bloques como máximo.
- Hasta 2 líneas «Etiqueta: hecho» por bloque.
- Sin matriz.
""",
    LENGTH_MEDIUM: """Nivel de longitud: MEDIO.
- Título + hasta 4 bloques.
- Hasta 4 líneas «Etiqueta: hecho» por bloque, más subbloques de contraste solo si el texto los sostiene.
- Cierra con la Matriz Resumen de Indicadores (hasta 4 filas, una por bloque).
""",
    LENGTH_LONG: """Nivel de longitud: DETALLADO.
- Título + hasta 4 bloques.
- Hasta 5 líneas «Etiqueta: hecho» por bloque. Sigue siendo denso, no un volcado.
- Una sola Matriz Resumen de Indicadores, hasta 4 filas.
""",
}

_SYSTEM_PROMPT_PRODUCT_CORE = """Eres un asistente que convierte MANUALES DE PRODUCTO / ELECTRODOMÉSTICOS
en fichas técnicas profesionales y CONCISAS en español.
Extrae solo hechos del texto y ordénalos exactamente en estas secciones (incluye todas).

Formato visual (texto plano, SIN Markdown):
- NO uses # ni ## ni ** ni _ de Markdown.
- PROHIBIDO el adorno «──» y la sección «Título / tema».
- Si hay marca o modelo, la primera línea es solo el nombre del producto (por ejemplo «EcoWash X200»), sin viñeta y sin etiqueta.
- Cada sección va sola en su línea, solo el nombre. Contenido en viñetas con «- ».

Secciones (en este orden; el nombre del producto, si existe, va antes):
Identificación
Especificaciones
Conexión / instalación
Programas
Uso diario
Mantenimiento
Códigos de error / averías
Advertencias importantes

Formato obligatorio (viñetas densas, sin relleno):
- Identificación: Marca, Modelo, Tipo, Referencia/Serie si aparecen.
- Especificaciones: Capacidad (kg), Velocidad de centrifugado (rpm), Potencia (W), Voltaje (V), Dimensiones (cm), Peso (kg). Formato «Capacidad: 8 kg».
- Programas: una viñeta por programa con nombre + uso + temp/rpm/duración si aparecen.
- Códigos de error: «E1 — descripción / solución».
- Si un dato no está en el texto, escribe exactamente: No indicado en el texto.
- No inventes. Prioriza hechos útiles frente a índice o tabla de contenidos.
- Español correcto, conciso, una idea por línea.
- Ordena números de forma consistente (p. ej. rpm de mayor a menor si hay varias; códigos E/F en orden).
"""

_LENGTH_PROMPT_PRODUCT = {
    LENGTH_SHORT: """Nivel de longitud: CORTO.
- Uso / mantenimiento / conexión / advertencias: máx. 3 viñetas útiles por sección.
- Programas: hasta 4 (los más representativos).
""",
    LENGTH_MEDIUM: """Nivel de longitud: MEDIO.
- Uso / mantenimiento / conexión / advertencias: máx. 6 viñetas útiles por sección.
""",
    LENGTH_LONG: """Nivel de longitud: DETALLADO.
- Uso / mantenimiento / conexión / advertencias: hasta 10 viñetas útiles por sección si aportan.
- Programas: incluye más ciclos si aparecen, sin duplicar.
""",
}


def _system_prompt(mode: str, length: str) -> str:
    length = normalize_length(length)
    if mode == "product":
        return _SYSTEM_PROMPT_PRODUCT_CORE + "\n" + _LENGTH_PROMPT_PRODUCT[length]
    return _SYSTEM_PROMPT_GENERIC_CORE + "\n" + _LENGTH_PROMPT_GENERIC[length]


# Compatibilidad con imports / tests que lean las constantes antiguas.
SYSTEM_PROMPT_GENERIC = _SYSTEM_PROMPT_GENERIC_CORE + "\n" + _LENGTH_PROMPT_GENERIC[LENGTH_MEDIUM]
SYSTEM_PROMPT_PRODUCT = _SYSTEM_PROMPT_PRODUCT_CORE + "\n" + _LENGTH_PROMPT_PRODUCT[LENGTH_MEDIUM]


@dataclass
class SummaryResult:
    text: str
    engine: str  # "api" | "local"
    note: str = ""
    mode: str = "generic"  # "generic" | "product"
    length: str = LENGTH_MEDIUM  # "short" | "medium" | "long"


@dataclass
class _Extracted:
    marca: str = ""
    modelo: str = ""
    tipo: str = ""
    referencia: str = ""
    capacidad: str = ""
    rpm: str = ""
    potencia: str = ""
    voltaje: str = ""
    dimensiones: str = ""
    peso: str = ""
    conexion: list[str] = field(default_factory=list)
    programas: list[str] = field(default_factory=list)
    uso: list[str] = field(default_factory=list)
    mantenimiento: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


_MD_HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NOISE_FICHA_TITLES = re.compile(
    r"(?i)^(?:ficha\s+del?\s+(?:texto|producto|manual)|resumen\s+del?\s+texto)\s*$"
)


_TITLE_SECTION = re.compile(r"(?i)^t[ií]tulo\s*/\s*tema$")
_RULE_HEADING = re.compile(r"^──\s*(.+?)\s*──$")


def _bare_heading(line: str) -> str | None:
    """Nombre de sección sin # ni rayas. None si la línea no es un encabezado marcado."""
    stripped = line.strip()
    marked = _MD_HEADING_LINE.match(stripped)
    if marked:
        title = marked.group(2).strip().strip("#").strip()
    else:
        ruled = _RULE_HEADING.match(stripped)
        if not ruled:
            return None
        title = ruled.group(1).strip()
    title = re.sub(r"^──\s*", "", title)
    title = re.sub(r"\s*──$", "", title).strip()
    return title


def _plainify_ficha(text: str) -> str:
    """Deja los nombres de sección solos, sin # ni «──».

    Si llega una sección «Título / tema», esa etiqueta desaparece y su viñeta
    pasa a ser la primera línea de la ficha.
    """
    out: list[str] = []
    lifted_title = ""
    expect_title_bullet = False
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if re.match(r"^#{1,6}\s*$", stripped):
            continue
        heading = _bare_heading(stripped)
        if heading is not None:
            if not heading or _NOISE_FICHA_TITLES.match(heading):
                continue
            if _TITLE_SECTION.match(heading):
                expect_title_bullet = True
                continue
            out.append(heading)
            continue
        if expect_title_bullet and stripped.startswith("- "):
            lifted_title = stripped[2:].strip()
            expect_title_bullet = False
            continue
        expect_title_bullet = False
        out.append(line)
    if lifted_title:
        existing = next((row.strip() for row in out if row.strip()), "")
        if existing != lifted_title:
            out = [lifted_title, ""] + out
    joined = "\n".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined).strip()
    return joined


def _finalize_ficha(text: str) -> str:
    return _plainify_ficha(correct_text(text))


def summarize_manual(
    text: str,
    *,
    use_api: bool = True,
    length: str = LENGTH_MEDIUM,
) -> SummaryResult:
    cleaned = (text or "").strip()
    length = normalize_length(length)
    if not cleaned:
        return SummaryResult(
            "No hay texto para resumir.", "local", mode="generic", length=length
        )

    mode = detect_document_mode(cleaned)

    if use_api:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return SummaryResult(
                _finalize_ficha(_local_summary(cleaned, mode, length=length)),
                "local",
                note="Sin OPENAI_API_KEY: ficha generada con motor local.",
                mode=mode,
                length=length,
            )
        api_result = _try_api_summary(cleaned, mode, length=length)
        if api_result is not None:
            return SummaryResult(
                _finalize_ficha(api_result), "api", mode=mode, length=length
            )
        return SummaryResult(
            _finalize_ficha(_local_summary(cleaned, mode, length=length)),
            "local",
            note="La API falló o no respondió: ficha generada con motor local.",
            mode=mode,
            length=length,
        )

    return SummaryResult(
        _finalize_ficha(_local_summary(cleaned, mode, length=length)),
        "local",
        mode=mode,
        length=length,
    )


def detect_document_mode(text: str) -> str:
    """Devuelve 'product' solo con señales fuertes de manual de aparato; si no, 'generic'."""
    score = _product_manual_score(text)
    return "product" if score >= _PRODUCT_CONFIDENCE_THRESHOLD else "generic"


def _product_manual_score(text: str) -> float:
    """Puntuación de confianza de que el texto es un manual de producto/electrodoméstico."""
    lower = text.lower()
    score = 0.0

    appliance = (
        "lavadora", "secadora", "lavavajillas", "frigorífico", "frigorifico",
        "nevera", "horno", "microondas", "vitrocerámica", "vitroceramica",
        "placa de inducción", "aire acondicionado", "calentador", "termo",
        "manual de usuario", "manual de instrucciones", "manual del producto",
    )
    if any(w in lower for w in appliance):
        score += 1.5

    # Campos etiquetados típicos de ficha técnica
    labeled = 0
    for pat in (
        r"(?i)\bmarca\s*:",
        r"(?i)\bmodelo\s*:",
        r"(?i)\bcapacidad\s*:",
        r"(?i)\bdimensiones?\s*:",
        r"(?i)\balimentaci[oó]n\s*:",
        r"(?i)\btipo\s*:\s*(carga\s+frontal|carga\s+superior)",
    ):
        if re.search(pat, text):
            labeled += 1
    if labeled >= 2:
        score += 2.0
    elif labeled == 1:
        score += 0.5

    # Capacidad + rpm (señal fuerte de lavadora/secadora)
    has_cap = bool(
        re.search(r"(?i)\bcapacidad\b[^.\n]{0,40}\d+(?:[.,]\d+)?\s*kg", text)
        or re.search(r"(?i)\d+(?:[.,]\d+)?\s*kg[^.\n]{0,30}\bcapacidad\b", text)
    )
    has_rpm = bool(re.search(r"(?i)\b\d{3,5}\s*rpm\b", text))
    if has_cap and has_rpm:
        score += 2.0
    elif has_rpm and any(w in lower for w in ("centrifug", "programa", "lavado")):
        score += 1.0

    # Programas de lavado / ciclos de aparato
    program_hits = sum(
        1
        for w in (
            "algodón", "algodon", "sintéticos", "sinteticos", "delicado",
            "centrifugado", "prelavado", "enjuague", "aclarado", "rápido 15",
            "rapido 15", "programa", "ciclos",
        )
        if w in lower
    )
    if program_hits >= 3:
        score += 2.0
    elif program_hits >= 2:
        score += 1.0

    # Instalación típica de electrodoméstico
    install_hits = sum(
        1
        for w in (
            "manguera", "desagüe", "desague", "agua fría", "agua fria",
            "cajetín", "cajetin", "tambor", "bloqueo infantil",
            "toma de 3/4", "grifo",
        )
        if w in lower
    )
    if install_hits >= 2:
        score += 2.0
    elif install_hits == 1:
        score += 0.5

    # Códigos de error de aparato (E1 — …) con contexto técnico
    error_codes = re.findall(
        r"(?i)\b(?:E|F|Err(?:or)?)\s*0*\d{1,2}\s*[:\-–—]",
        text,
    )
    if len(error_codes) >= 2:
        score += 1.5
    elif len(error_codes) == 1 and install_hits:
        score += 0.5

    # Penalizar textos claramente académicos / ensayísticos sin señales de producto
    academic = (
        "teoría", "teoria", "economía", "economia", "escasez", "ensayo",
        "dosier", "dossier", "concepto", "definición", "definicion",
        "hipótesis", "hipotesis", "capítulo", "capitulo", "bibliografía",
        "bibliografia", "introducción", "introduccion", "conclusión",
        "conclusion", "implicaciones", "análisis", "analisis",
    )
    acad_hits = sum(1 for w in academic if w in lower)
    if acad_hits >= 2 and score < 3.0:
        score -= 1.5

    return score


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


def _try_api_summary(
    text: str, mode: str, *, length: str = LENGTH_MEDIUM
) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    length = normalize_length(length)
    model = os.getenv("FICHAMANUAL_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    client = OpenAI(api_key=api_key)
    chunks = _chunk_text(text)
    partials: list[str] = []
    system = _system_prompt(mode, length)
    kind = "manual de producto" if mode == "product" else "texto"
    length_label = {
        LENGTH_SHORT: "corta",
        LENGTH_MEDIUM: "media",
        LENGTH_LONG: "detallada",
    }[length]

    try:
        for i, chunk in enumerate(chunks, start=1):
            if mode == "generic":
                brevity = (
                    f"Respeta el nivel de longitud {length_label}: "
                    "síntesis de hits, no volcado del texto. "
                )
            else:
                brevity = (
                    f"Respeta el nivel de longitud {length_label}: "
                    "solo hechos útiles. "
                )
            user = (
                f"Parte {i}/{len(chunks)} del {kind}. "
                f"{brevity}"
                "Extrae lo importante en formato de ficha "
                "(mismas secciones y reglas del sistema):\n\n"
                f"{chunk}"
            )
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
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

        if mode == "generic":
            merge_prompt = (
                "Combina estas fichas parciales en UNA sola ficha analítica, "
                "sin duplicar ni inventar cifras, leyes ni estadísticas. "
                "Formato: título sintetizado; bloques numerados con líneas «Etiqueta: hecho»; "
                "subbloques de contraste solo si el texto los sostiene; "
                "cierra con Matriz Resumen de Indicadores "
                "(Dimensión | Factor clave | Indicador de control) solo con hechos presentes. "
                f"Mantén la longitud {length_label}. "
                "Omite LaTeX, citas [n] y ruido de Wikipedia.\n\n"
                + "\n\n---\n\n".join(partials)
            )
        else:
            merge_prompt = (
                "Combina estas fichas parciales en UNA sola ficha final, "
                "sin duplicar datos, usando exactamente las mismas secciones y reglas. "
                f"Mantén la longitud {length_label}: elimina relleno, LaTeX, citas [n] "
                "y viñetas repetidas. "
                "Cada viñeta debe ser una frase completa; si no cabe, omítela. "
                f"Si un dato de producto no aparece en ninguna parcial, usa: {MISSING}\n\n"
                + "\n\n---\n\n".join(partials)
            )
        merged = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": merge_prompt},
            ],
        )
        return (merged.choices[0].message.content or "").strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Motor local — enrutado
# ---------------------------------------------------------------------------

def _local_summary(
    text: str,
    mode: str | None = None,
    *,
    length: str = LENGTH_MEDIUM,
) -> str:
    if mode is None:
        mode = detect_document_mode(text)
    length = normalize_length(length)
    if mode == "product":
        caps = _length_caps(length)
        data = _extract_all(
            text,
            bullet_limit=caps["product_bullets"],
            program_limit=caps["product_programs"],
        )
        return _format_ficha_product(data)
    return _format_ficha_generic(text, length=length)


# ---------------------------------------------------------------------------
# Motor local — ficha genérica
# ---------------------------------------------------------------------------

_TOC_NOISE = re.compile(
    r"^(índice|indice|tabla de contenidos|contenido|sumario|"
    r"capítulo|capitulo|página|pagina|\d+\s*[.\)]\s*$)",
    re.I,
)
_WEB_NAV_NOISE = re.compile(
    r"(?i)^(artículo principal|articulo principal|véase también|vease tambien|"
    r"referencias|bibliografía|bibliografia|enlaces externos|notas|categoría|"
    r"categoria|plantilla:|cita requerida|editar|ocultar|mostrar)\b"
)
_SECTION_TITLE_NOISE = re.compile(
    r"(?i)^(clasificaci[oó]n(?:\s+de(?:\s+los)?\s+sistemas?)?|historia|"
    r"introducci[oó]n|definici[oó]n|etimolog[ií]a|notas?|anexos?|"
    r"l[ií]mites?\s+de\s+predicci[oó]n|sensibilidad\s+a\s+las\s+condiciones|"
    r"v[eé]ase\s+tambi[eé]n|referencias|bibliograf[ií]a)\s*$"
)
_LATEX_RESIDUE_LINE = re.compile(
    r"(?i)^(?:donde|en\s+la\s+que|siendo|con)\s+"
    r"(?:\\?[a-zA-Z]+|el|la|los|las|un|una)?\s*"
    r"(?:es|son|denota|representa)\b"
)
_LATEX_COMMAND = re.compile(
    r"\\(?:displaystyle|frac|cdot|times|begin|end|left|right|mathrm|mathbf|"
    r"text|operatorname|overline|underline|sum|prod|int|lim|sqrt|delta|lambda|"
    r"alpha|beta|gamma|theta|infty|partial|nabla|ln|log|sin|cos|tan)\b",
    re.I,
)


def _remove_display_math(text: str) -> str:
    """Elimina grupos de presentación LaTeX como {\\displaystyle ...}."""
    token = "{\\displaystyle"
    output: list[str] = []
    cursor = 0
    while True:
        start = text.find(token, cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start])
        depth = 0
        end = start
        while end < len(text):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        cursor = end
        output.append(" ")
    return "".join(output)


def _is_math_noise(text: str) -> bool:
    s = text.strip()
    if _LATEX_COMMAND.search(s) or re.search(r"\\[A-Za-z]+|\{\\|\$\$?", s):
        return True
    # Residuo LaTeX corto («Donde λ es…»); no tumbar líneas largas con prosa útil
    if len(s) < 140 and _LATEX_RESIDUE_LINE.match(s):
        return True
    if len(s) < 100 and re.match(r"(?i)^donde\s+es\b", s):
        return True
    compact = re.sub(r"\s+", "", s)
    return len(compact) >= 12 and sum(ch in "{}_^=<>\\" for ch in compact) / len(compact) > 0.12


def _is_web_residue(text: str) -> bool:
    """Residuos de Wikipedia / páginas web que no son contenido útil."""
    s = text.strip()
    if not s:
        return True
    if _WEB_NAV_NOISE.match(s):
        return True
    if re.match(r"(?i)^artículo principal\s*:", s) or re.match(r"(?i)^articulo principal\s*:", s):
        return True
    # Listas de «véase también» de una o dos palabras
    if len(s.split()) <= 3 and not re.search(r"[.!?]", s):
        if re.match(
            r"(?i)^(fractales?|atractores?\s+extra[nñ]os?|sistemas?\s+din[aá]micos?|"
            r"efecto\s+mariposa|lyapunov|lorenz)$",
            s,
        ):
            return True
    return False

_HEADING_LINE = re.compile(
    r"(?i)^(?:#{1,6}\s+|[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\s]{3,}$|"
    r".{3,80}$)"
)

_DEF_PATTERNS = (
    re.compile(
        r"(?i)\b([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\w\-áéíóúñü]{3,40})\s+"
        r"es\s+(el concepto\b.+)"
    ),
    re.compile(
        r"(?i)\b([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\w\-áéíóúñü]{3,40})\s+"
        r"(?:se define como|consiste en|significa|denota)\s+(.+)"
    ),
    re.compile(
        r"(?i)^([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\w\-áéíóúñü\s]{2,40}?)\s*:\s*"
        r"(.{20,200})$"
    ),
)

_NUMBER_FACT = re.compile(
    r"(?i)(?:^|[.\n]\s*)([^.!?\n]{10,220}?"
    r"(?:\d+(?:[.,]\d+)?\s*%|"
    r"\d+(?:[.,]\d+)?\s*(?:millones?|mil|billones?)|"
    r"(?:siglo|año|años)\s+\d{2,4}|"
    r"\d{4}"
    r")[^.!?\n]{0,120})"
)

_CONCLUSION_STRONG = (
    "en conclusión", "en conclusion", "en resumen", "en definitiva",
    "se concluye", "como resultado", "para concluir", "a modo de conclusión",
    "a modo de conclusion",
)
_CONCLUSION_SOFT = (
    "por tanto", "por lo tanto", "así pues", "asi pues",
    "implica", "implicación", "implicacion", "consecuencia", "finalmente",
)
_CONCLUSION_KW = _CONCLUSION_STRONG + _CONCLUSION_SOFT


def _normalize_lines(text: str) -> list[str]:
    raw = _clean_raw_text(text)
    lines: list[str] = []
    for line in raw.split("\n"):
        cleaned = re.sub(r"\s+", " ", line).strip(" \u2022*-\u2013\u2014\t# ")
        if len(cleaned) < 3:
            continue
        if _is_math_noise(cleaned) or _is_web_residue(cleaned):
            continue
        if re.fullmatch(r"[=_\-]{3,}", cleaned):
            continue
        if _TOC_NOISE.match(cleaned):
            continue
        if re.fullmatch(r"[\d.\-/]+", cleaned):
            continue
        # No truncar aquí: las frases largas se parten en oraciones después
        if len(cleaned) > 500:
            cleaned = cleaned[:500]
        lines.append(cleaned)
    return lines


def _clean_raw_text(text: str) -> str:
    """Limpia artefactos frecuentes al copiar páginas web y fórmulas LaTeX."""
    raw = _remove_display_math(text)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"\[\s*\d{1,3}\s*\]", "", raw)
    raw = re.sub(r"\\(?:displaystyle|left|right)\b", "", raw)
    # Comandos LaTeX sueltos (\\frac{a}{b}, \\ln, etc.)
    raw = re.sub(r"\\[A-Za-z]+\*?(?:\s*\{[^{}]*\})*", " ", raw)
    raw = re.sub(r"\{([^{}]{1,40})\}", r"\1", raw)
    cleaned_lines: list[str] = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if re.fullmatch(r"[=_\-─—]{3,}", stripped):
            cleaned_lines.append("")
            continue
        # Quitar subrayado pegado al final de una línea de título
        stripped = re.sub(r"\s*[=_\-─—]{3,}\s*$", "", stripped)
        if _is_web_residue(stripped):
            cleaned_lines.append("")
            continue
        # Fórmulas puras: descartar. Residuo «Donde λ…» al inicio: recortar oración
        if _is_math_noise(stripped) and len(stripped) < 140:
            cleaned_lines.append("")
            continue
        if _LATEX_RESIDUE_LINE.match(stripped) or re.match(r"(?i)^donde\s+(?:\\?\w+\s+)?es\b", stripped):
            # Conservar prosa posterior a la primera oración-residuo
            parts = re.split(r"(?<=[.!?])\s+", stripped, maxsplit=1)
            if len(parts) == 2 and len(parts[1]) >= 20:
                cleaned_lines.append(parts[1])
                continue
            cleaned_lines.append("")
            continue
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\\(?:delta|lambda|alpha|beta|gamma|theta)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\\(?:cdot|times|infty|partial|nabla|ln|log)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\$\$?([^$]*)\$\$?", " ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def _split_sentences(text: str) -> list[str]:
    raw = _clean_raw_text(text)
    paras = re.split(r"\n\s*\n+", raw)
    sentences: list[str] = []
    for para in paras:
        chunk = re.sub(r"\s+", " ", para).strip()
        chunk = re.sub(r"\s*[=_\-─—]{3,}\s*", " ", chunk).strip()
        if len(chunk) < 20:
            if (
                chunk
                and len(chunk) >= 8
                and not re.fullmatch(r"[=_\-─—]+", chunk)
                and not _is_math_noise(chunk)
                and not _is_web_residue(chunk)
                and not _SECTION_TITLE_NOISE.match(chunk)
            ):
                sentences.append(chunk)
            continue
        parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑÜ¿¡\"'])", chunk)
        for p in parts:
            s = p.strip()
            if _is_math_noise(s) or _is_web_residue(s):
                continue
            if re.search(r"[=_\-─—]{3,}", s):
                s = re.sub(r"\s*[=_\-─—]{3,}\s*", " ", s).strip()
            if _SECTION_TITLE_NOISE.match(s) or _is_heading_like_fragment(s):
                continue
            if len(s) >= 20:
                sentences.append(s)
            elif len(s) >= 18 and s not in sentences:
                sentences.append(s)
    return sentences


def _is_heading_like_fragment(text: str) -> bool:
    """Encabezados o rótulos cortos que no son ideas resumibles."""
    s = text.strip().rstrip(".")
    if _SECTION_TITLE_NOISE.match(s) or _WEB_NAV_NOISE.match(s):
        return True
    if re.match(r"(?i)^(wikipedia\b|\w{2,40},\s*[A-Z]\.\s*\(\d{4}\))", s):
        return True
    words = s.split()
    if len(words) <= 8 and not re.search(r"[.!?]", text) and not re.search(
        r"(?i)\b(es|son|est[aá]|estan|est[aá]n|fue|fueron|tiene|tienen|puede|pueden|"
        r"implica|estudia|trata|describe|consiste|significa|descubri\w*|"
        r"ilustra|resulta|permite|aunque|cuando|porque|era|eran)\b",
        s,
    ):
        # Sin verbo predicativo → probablemente rótulo de sección
        if len(words) <= 6 and not re.search(r"\d", s):
            return True
    return False


def _is_heading_candidate(line: str, *, short_ok: bool = True) -> bool:
    s = line.strip()
    if len(s) < 4 or len(s) > 90:
        return False
    if s.endswith("."):
        return False
    if _is_math_noise(s) or _is_web_residue(s):
        return False
    words = s.split()
    if len(words) > 12:
        return False
    # Título en mayúsculas o pocas palabras sin verbo largo
    if s.isupper() and len(words) <= 10:
        return True
    if short_ok and len(words) <= 8 and not re.search(r"\d{2,}", s):
        # Evitar frases completas con muchos conectores
        lower = s.lower()
        if any(c in lower for c in (" que ", " porque ", " cuando ", " donde ")):
            return False
        return True
    return False


def _topic_from_definition(sentence: str) -> str | None:
    """Extrae el tema de definiciones del tipo «La X es la/el/una…»."""
    patterns = (
        r"(?i)^(?:la|el|los|las)\s+(.{3,80}?)\s+(?:es|son)\s+"
        r"(?:la|el|un|una|los|las)\s+(?:rama|estudio|conjunto|disciplina|ciencia|"
        r"teoría|teoria|concepto|propiedad|área|area|campo)\b",
        r"(?i)^(?:la|el|los|las)\s+(.{3,80}?)\s+(?:es|son)\s+"
        r"(?:la|el|un|una|los|las)\b",
        r"(?i)^(.{3,60}?)\s+(?:se define como|consiste en|estudia|trata)\b",
    )
    for pat in patterns:
        match = re.match(pat, sentence)
        if not match:
            continue
        topic = match.group(1).strip(" ,:;.")
        topic = re.sub(r"(?i)^(?:la|el|los|las)\s+", "", topic).strip()
        nwords = len(topic.split())
        if 1 <= nwords <= 9 and not _SECTION_TITLE_NOISE.match(topic):
            return topic[:1].upper() + topic[1:]
    return None


def _opening_title(lines: list[str]) -> str | None:
    """Título del documento si está al principio, no un apartado interno."""
    for line in lines[:6]:
        if (
            _GENERIC_HEADING.match(line)
            or _SECTION_TITLE_NOISE.match(line)
            or _is_web_residue(line)
            or _is_math_noise(line)
        ):
            continue
        if line.endswith(".") or len(line) > 90:
            break
        words = line.split()
        if 2 <= len(words) <= 12 and (
            _is_heading_candidate(line) or _is_heading_like_fragment(line)
        ):
            return line.strip().rstrip(".")
        break
    return None


def _guess_title(lines: list[str], text: str) -> str:
    """Identifica el tema central, no el primer encabezado de sección."""
    sentences = _split_sentences(text)

    opening = _opening_title(lines)
    if opening:
        return opening[:1].upper() + opening[1:]

    # 1) Definiciones explícitas en cualquier parte temprana del texto
    for sentence in sentences[:20]:
        topic = _topic_from_definition(sentence)
        if topic:
            richer = _title_from_heading(topic, lines)
            return richer or topic

    # 2) Frases con «teoría / concepto / principio de X» frecuentes
    topic_hits: dict[str, int] = {}
    for sentence in sentences:
        for m in re.finditer(
            r"(?i)\b((?:teor[ií]a|concepto|principio|ley|modelo|sistema)\s+del?\s+[a-záéíóúñü][\w\-áéíóúñü]{2,30})",
            sentence,
        ):
            key = m.group(1).strip().lower()
            topic_hits[key] = topic_hits.get(key, 0) + 1
        for m in re.finditer(
            r"(?i)\b(teor[ií]a\s+del?\s+[a-záéíóúñü][\w\-áéíóúñü]{2,30})",
            sentence,
        ):
            key = m.group(1).strip().lower()
            topic_hits[key] = topic_hits.get(key, 0) + 2
    if topic_hits:
        best = max(topic_hits.items(), key=lambda kv: (kv[1], len(kv[0])))[0]
        return best[:1].upper() + best[1:]

    # 3) Primer título real del documento, no un apartado genérico (Historia, Índice…)
    for line in lines[:8]:
        lower = line.lower()
        if (
            _SECTION_TITLE_NOISE.match(line)
            or _GENERIC_HEADING.match(line)
            or _is_web_residue(line)
        ):
            continue
        if lower.startswith(("marca:", "modelo:", "capacidad:")):
            continue
        if re.search(r"[=_\-─—]{3,}", line):
            continue
        words = line.split()
        if 2 <= len(words) <= 12 and (
            _is_heading_candidate(line) or _is_heading_like_fragment(line)
        ):
            return line.strip().rstrip(".")

    # 4) Primera oración útil (completa, sin truncar)
    for sentence in sentences:
        if _is_heading_like_fragment(sentence) or _is_web_residue(sentence):
            continue
        if len(sentence) <= 110:
            return sentence.rstrip(".")
        # Tomar solo la primera cláusula completa si es larga
        clause = _first_complete_clause(sentence, max_len=110)
        if clause:
            return clause
    return "Texto sin título explícito"


def _title_from_heading(topic: str, lines: list[str]) -> str | None:
    """Si un título temprano precisa el tema («Escasez» → «La escasez en economía»), úsalo."""
    tokens = [
        tok
        for tok in re.findall(r"[a-záéíóúñü]{4,}", topic.lower())
        if tok not in _RANK_STOP
    ]
    if not tokens:
        return None
    for line in lines[:12]:
        if (
            _SECTION_TITLE_NOISE.match(line)
            or _GENERIC_HEADING.match(line)
            or _is_web_residue(line)
            or _is_math_noise(line)
        ):
            continue
        if not (_is_heading_candidate(line) or _is_heading_like_fragment(line)):
            continue
        low = line.lower()
        if not all(tok in low for tok in tokens):
            continue
        if len(topic.split()) < len(line.split()) <= 12:
            cleaned = line.strip().rstrip(".")
            return cleaned[:1].upper() + cleaned[1:]
    return None


def _extract_section_headings(lines: list[str]) -> list[str]:
    """Apartados de contenido; excluye navegación web y rótulos irrelevantes."""
    headings: list[str] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        if not _is_heading_candidate(line, short_ok=True):
            continue
        if len(line.split()) > 8 or len(line) > 70:
            continue
        if _SECTION_TITLE_NOISE.match(line) or _is_web_residue(line):
            # Algunos títulos de sección sí aportan (p. ej. sensibilidad…):
            # solo aceptar si hay prosa útil a continuación y no es nav/wiki.
            if _WEB_NAV_NOISE.match(line) or re.match(
                r"(?i)^(clasificaci[oó]n|historia|referencias|bibliograf|"
                r"v[eé]ase|notas?|anexos?|introducci[oó]n|etimolog)",
                line,
            ):
                continue
        key = line.lower()
        if key in seen:
            continue
        # Debe haber al menos una línea de contenido después
        has_body = False
        for nxt in lines[i + 1 : i + 4]:
            if _is_heading_candidate(nxt) or _is_web_residue(nxt) or _is_math_noise(nxt):
                continue
            if len(nxt) >= 40:
                has_body = True
                break
        if not has_body:
            continue
        seen.add(key)
        headings.append(line)
        if len(headings) >= 6:
            break
    return headings


# Palabras vacías: la comparación de frases usa el contenido, no la gramática.
_RANK_STOP = frozenset(
    {
        "una", "uno", "unas", "unos", "para", "como", "pero", "más", "mas",
        "sus", "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso",
        "esos", "esas", "muy", "también", "tambien", "entre", "cuando", "donde",
        "desde", "hasta", "sobre", "tras", "porque", "aunque", "además", "ademas",
        "hacia", "durante", "mediante", "según", "segun", "sin", "con", "por",
        "del", "las", "los", "que", "qué", "cual", "cuales", "cada", "otro",
        "otra", "otros", "otras", "mismo", "misma", "todo", "toda", "todos",
        "todas", "hay", "son", "está", "estan", "están", "fue", "fueron", "ser",
        "sido", "puede", "pueden", "debe", "deben", "así", "asi", "pues",
        "the", "and", "for", "with", "that", "this", "from",
    }
)

_GENERIC_HEADING = re.compile(
    r"(?i)^(clasificaci[oó]n|historia|introducci[oó]n|definici[oó]n|"
    r"etimolog[ií]a|notas?|anexos?|v[eé]ase\s+tambi[eé]n|referencias|"
    r"bibliograf[ií]a|enlaces externos|contenido|sumario|índice|indice)\b"
)


def _score_key_sentence(s: str) -> float:
    """Señales de forma (definición, cifra, cierre). No depende del tema."""
    lower = s.lower()
    score = 0.0
    if lower.startswith(("donde ", "esto es, donde ")):
        score -= 2.0
    if _is_web_residue(s) or _is_math_noise(s) or _is_heading_like_fragment(s):
        score -= 8.0
    if re.search(
        r"(?i)\b(se define|consiste en|significa|es la|es el|es un|es una)\b",
        s,
    ):
        score += 1.2
    if re.search(r"\d", s):
        score += 0.6
    if any(w in lower for w in _CONCLUSION_STRONG):
        score += 1.5
    elif any(w in lower for w in _CONCLUSION_SOFT):
        score += 0.4
    n = len(s)
    if 40 <= n <= 240:
        score += 0.8
    elif n > 320:
        score -= 0.5
    if _TOC_NOISE.match(s):
        score -= 5.0
    return score


def _content_token_list(text: str) -> list[str]:
    return [
        tok
        for tok in re.findall(r"[a-záéíóúñü0-9]{3,}", text.lower())
        if tok not in _RANK_STOP
    ]


def _content_tokens(text: str) -> set[str]:
    return set(_content_token_list(text))


def _too_similar(a: str, b: str) -> bool:
    """True si dos frases dicen la misma idea, no solo si comparten el tema."""
    if _overlap_ratio(a, b) >= 0.55:
        return True
    if _overlap_ratio(a, b) < 0.28:
        return False
    left = _content_token_list(a)
    right = _content_token_list(b)
    if len(left) < 3 or len(right) < 3:
        return False
    shared = set(zip(left, left[1:], left[2:])) & set(zip(right, right[1:], right[2:]))
    return bool(shared)
    return {
        tok
        for tok in re.findall(r"[a-záéíóúñü0-9]{3,}", text.lower())
        if tok not in _RANK_STOP
    }


def _centrality(sentences: list[str]) -> list[float]:
    """Importancia de cada frase dentro de este texto.

    Sube si comparte contenido con otras frases y si usa términos que el
    propio documento repite. No hay una lista de temas privilegiados.
    """
    n = len(sentences)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    token_sets = [_content_tokens(s) for s in sentences]
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        if not token_sets[i]:
            continue
        for j in range(i + 1, n):
            if not token_sets[j]:
                continue
            inter = len(token_sets[i] & token_sets[j])
            if inter == 0:
                continue
            score = inter / len(token_sets[i] | token_sets[j])
            if score < 0.06:
                continue
            sim[i][j] = sim[j][i] = score

    weight = [sum(row) for row in sim]
    rank = [1.0 / n] * n
    for _ in range(24):
        nxt = [(1.0 - 0.85) / n] * n
        for i in range(n):
            incoming = 0.0
            for j in range(n):
                if sim[j][i] and weight[j]:
                    incoming += rank[j] * sim[j][i] / weight[j]
            nxt[i] += 0.85 * incoming
        rank = nxt

    df: dict[str, int] = {}
    for toks in token_sets:
        for tok in toks:
            df[tok] = df.get(tok, 0) + 1
    focus: list[float] = []
    for toks in token_sets:
        if not toks:
            focus.append(0.0)
            continue
        focus.append(sum(df[tok] for tok in toks) / len(toks))

    max_rank = max(rank) or 1.0
    max_focus = max(focus) or 1.0
    return [
        0.62 * (rank[i] / max_rank) + 0.38 * (focus[i] / max_focus)
        for i in range(n)
    ]


def _prepare_line(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip(" \u2022*-\u2013\u2014\t# ")
    if len(cleaned) < 3:
        return ""
    if _is_math_noise(cleaned) or _is_web_residue(cleaned):
        return ""
    if re.fullmatch(r"[=_\-─—]{3,}", cleaned):
        return ""
    if _TOC_NOISE.match(cleaned) or re.fullmatch(r"[\d.\-/]+", cleaned):
        return ""
    if len(cleaned) > 800:
        cleaned = cleaned[:800]
    return cleaned


def _sentences_in_chunk(chunk: str) -> list[str]:
    chunk = re.sub(r"\s+", " ", chunk).strip()
    if len(chunk) < 20:
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑÜ¿¡\"'])", chunk)
    return [part.strip() for part in parts if len(part.strip()) >= 20]


def _is_section_heading(line: str) -> bool:
    """Rótulo de apartado. Una frase cortada por el ancho de línea no cuenta."""
    if line.endswith(".") or len(line) > 90 or len(line.split()) > 10:
        return False
    if re.search(r"(?i)\b(que|porque|cuando|donde|aunque)\b", line):
        return False
    # Solo verbos claros. El detector amplio confunde «Historia» o «economía».
    if re.search(
        r"(?i)\b(es|son|est[aá]n?|fue|fueron|tiene|tienen|puede|pueden|"
        r"debe|deben|hay|era|eran|se\s+\w+)\b",
        line,
    ):
        return False
    return _is_heading_candidate(line) or _is_heading_like_fragment(line)


def _iter_content_units(text: str) -> list[dict]:
    """Frases útiles, uniendo líneas partidas y respetando los apartados."""
    units: list[dict] = []
    section = 0
    heading = ""
    lead = True
    buffer: list[str] = []

    def flush() -> None:
        nonlocal lead
        if not buffer:
            return
        chunk = " ".join(buffer)
        buffer.clear()
        for sentence in _sentences_in_chunk(chunk):
            if (
                _is_web_residue(sentence)
                or _is_math_noise(sentence)
                or _is_heading_like_fragment(sentence)
                or sentence[0].islower()
            ):
                continue
            units.append(
                {
                    "text": sentence,
                    "section": section,
                    "heading": heading,
                    "lead": lead,
                }
            )
            lead = False
        buffer.clear()

    for raw_line in _clean_raw_text(text).split("\n"):
        line = _prepare_line(raw_line)
        if not line:
            flush()
            continue
        if _is_section_heading(line):
            flush()
            section += 1
            heading = line
            lead = True
            continue
        buffer.append(line)
    flush()
    return units


def _unit_score(unit: dict, centrality: float) -> float:
    text = unit["text"]
    score = centrality
    if unit["lead"]:
        score += 0.12
    score += max(0.0, _score_key_sentence(text)) * 0.08
    if re.search(r"(?i)\b(se define como|consiste en|es la|es el|es un|es una)\b", text):
        score += 0.22
    # Hechos concretos (año, nombre propio): suelen ser el ejemplo que ancla el tema
    # y el grafo los baja porque no se repiten.
    if re.search(r"\b(?:1[5-9]\d{2}|20\d{2})\b", text):
        score += 0.16
    if re.search(
        r"\b[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}\b",
        text,
    ):
        score += 0.14
    return score


def _select_diverse(
    units: list[dict],
    limit: int,
    exclude: list[str] | None = None,
    *,
    coverage: bool = False,
) -> list[str]:
    """Elige hasta `limit` frases, en orden del texto, sin repetir la idea.

    Con cobertura, reserva un hueco al mejor hit de cada apartado de contenido
    antes de rellenar con las frases más centrales del documento.
    """
    if limit <= 0 or not units:
        return []

    banned = [item for item in (exclude or []) if item]
    ranks = _centrality([unit["text"] for unit in units])
    scored = [(_unit_score(unit, ranks[i]), i) for i, unit in enumerate(units)]
    best = max((score for score, _ in scored), default=1.0) or 1.0

    def cleaned_of(index: int) -> str:
        text = _compress_hit(units[index]["text"])
        if len(text) < 12 or not _looks_complete_phrase(text):
            return ""
        return text

    def richness(index: int) -> int:
        return len(_content_token_list(units[index]["text"]))

    chosen: list[int] = []

    def try_add(index: int) -> None:
        cleaned = cleaned_of(index)
        if not cleaned or index in chosen:
            return
        if any(_too_similar(cleaned, other) for other in banned):
            return
        conflict = None
        for kept in chosen:
            other = cleaned_of(kept) or units[kept]["text"]
            if not _too_similar(cleaned, other):
                continue
            if conflict is not None:
                return
            conflict = kept
        if conflict is None:
            if len(chosen) < limit:
                chosen.append(index)
            return
        # Misma idea: quédate con la frase que aporta más contenido.
        if richness(index) >= richness(conflict) + 3:
            chosen[chosen.index(conflict)] = index

    # Se recorre todo el ranking: una frase más baja puede sustituir a otra
    # si dice lo mismo y aporta más contenido.
    for _score, index in sorted(scored, key=lambda item: (-item[0], item[1])):
        try_add(index)

    if coverage and len(chosen) < limit:
        by_section: dict[int, list[tuple[float, int]]] = {}
        represented = {units[index]["section"] for index in chosen}
        for score, index in scored:
            heading = units[index]["heading"]
            if heading and _GENERIC_HEADING.match(heading):
                continue
            if units[index]["section"] in represented:
                continue
            by_section.setdefault(units[index]["section"], []).append((score, index))
        if len(by_section) >= 1:
            for cands in by_section.values():
                if len(chosen) >= limit:
                    break
                cands.sort(key=lambda item: (-item[0], item[1]))
                for score, index in cands:
                    if score < best * 0.52:
                        break
                    try_add(index)
                    break

    chosen.sort()
    out: list[str] = []
    for index in chosen:
        cleaned = _compress_hit(units[index]["text"])
        if cleaned:
            out.append(cleaned)
    return out[:limit]


_FILLER_START = (
    "es importante destacar", "cabe señalar", "cabe destacar",
    "es necesario", "como es sabido", "en este sentido",
    "de hecho", "por otro lado", "por otra parte",
    "así mismo", "asimismo", "en primer lugar", "en segundo lugar",
    "vale la pena", "resulta evidente", "es evidente que",
)


def _token_set(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-záéíóúñü0-9]{3,}", s.lower()) if t}


def _overlap_ratio(a: str, b: str) -> float:
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def _is_filler(s: str) -> bool:
    lower = s.lower().strip()
    if any(lower.startswith(f) for f in _FILLER_START):
        return True
    # Frases demasiado genéricas / vacías (sin cifras)
    if len(_token_set(lower)) < 3 and not re.search(r"\d", lower):
        return True
    return False


_DANGLING_TAIL = frozenset(
    {
        "a", "al", "ante", "bajo", "con", "contra", "de", "del", "desde", "durante",
        "e", "el", "en", "entre", "hacia", "hasta", "la", "las", "lo", "los",
        "mediante", "ni", "o", "para", "por", "según", "segun", "sin", "sobre",
        "tras", "un", "una", "unos", "unas", "y", "u", "que", "se", "su", "sus",
        "más", "mas", "menos", "como", "vs", "vs.", "versus", "the", "of", "and",
        "or", "to", "in", "on", "for", "with", "at", "by",
    }
)


def _trim_dangling_tail(s: str) -> str:
    """Evita cortes tipo «Recursos finitos vs» o «necesidades ilimitadas» a medias."""
    text = s.rstrip(" ,;:…")
    while text:
        parts = text.rsplit(" ", 1)
        if len(parts) == 1:
            break
        last = parts[1].lower().strip(".,;:…")
        if last in _DANGLING_TAIL or len(last) <= 1:
            text = parts[0].rstrip(" ,;:")
            continue
        break
    return text


_VERBISH = re.compile(
    r"(?i)\b("
    r"es|son|est[aá]|estan|est[aá]n|fue|fueron|tiene|tienen|"
    r"puede|pueden|implica|estudia|trata|describe|consiste|significa|"
    r"descubri\w*|ilustra|resulta|permite|aunque|cuando|porque|deben?|hay|"
    r"era|eran|no\s+es|se\s+\w+|"
    r"desaparece|desaparecen|cambia|cambian|crece|crecen|"
    r"transmite|transmiten|ayuda|ayudan|reconoce|reconocen|"
    r"prioriza|priorizan|genera|generan|renuncia|renuncian|"
    r"clasifica|exige|incluye|confirma|empieza|"
    # Otras conjugaciones verbales típicas (evitar sustantivos cortos en -a/-o)
    r"\w{4,}(?:ando|endo|ado|idos?|adas?|aba|[ií]an?|[oó]|i[oó]|"
    r"ar[aá]|er[aá]|ir[aá]|ce|cen|za|zan|yen|nen|ifica|izan?|"
    r"uye|uyen|ige|igen)"
    r")\b"
)


def _looks_complete_phrase(s: str) -> bool:
    """True si la viñeta parece una frase usable (no cortada a medias)."""
    text = s.strip()
    if len(text) < 12:
        return False
    if text.endswith("…") or text.endswith("..."):
        return False
    # Fragmentos huérfanos tras limpiar LaTeX/web
    if text[0].islower() and not text.startswith(("http", "www")):
        return False
    tail = text.rsplit(" ", 1)[-1].lower().strip(".,;:…")
    if tail in _DANGLING_TAIL:
        return False
    if re.match(r"(?i)^(wikipedia\b|\w{2,40},\s*[A-Z]\.\s*\(\d{4}\))", text):
        return False
    # Debe tener algún predicado o ser definición «X: …»
    if ":" in text and len(text.split(":", 1)[0].split()) <= 6:
        return len(text.split(":", 1)[1].strip()) >= 12
    if not _VERBISH.search(text):
        return False
    return True


def _first_complete_clause(s: str, max_len: int = 140) -> str:
    """Devuelve la primera cláusula completa ≤ max_len, o '' si no hay.

    Solo corta en separadores fuertes (. ; — :). Nunca en comas (evita
    «es la rama de las matemáticas» a medias).
    """
    cleaned = re.sub(r"\s+", " ", s).strip().rstrip(".")
    if len(cleaned) <= max_len and _looks_complete_phrase(cleaned):
        return _trim_dangling_tail(cleaned)
    for sep in (". ", "; ", " — ", " – ", ": "):
        idx = cleaned.find(sep)
        if idx >= 24:
            candidate = _trim_dangling_tail(cleaned[:idx].rstrip(" ,;:"))
            if len(candidate) <= max_len and _looks_complete_phrase(candidate):
                return candidate
    # Sin corte seguro → omitir (mejor que truncar)
    return ""


def _compress_hit(s: str, max_len: int = 140) -> str:
    """Reduce a un hit denso y completo. Si no cabe sin truncar, devuelve ''."""
    cleaned = re.sub(r"\s+", " ", s).strip().rstrip(".")
    cleaned = re.sub(r"\s*[=_\-─—]{3,}\s*", " ", cleaned).strip()
    cleaned = re.sub(r'[«"]([^»"]{80,})[»"]', r"\1", cleaned)
    if _is_math_noise(cleaned) or _is_web_residue(cleaned) or _is_heading_like_fragment(cleaned):
        return ""
    lower = cleaned.lower()
    for f in _FILLER_START:
        if lower.startswith(f):
            cleaned = cleaned[len(f):].lstrip(" ,:;¿¡-")
            cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
            break
    if not cleaned:
        return ""
    # Preferir la oración completa (hasta ~260) antes que truncar o omitir
    soft_max = max(max_len, 260)
    if len(cleaned) <= soft_max:
        out = _trim_dangling_tail(cleaned)
        return out if _looks_complete_phrase(out) else ""
    # Separador fuerte; nunca devolver frase truncada con «…»
    return _first_complete_clause(cleaned, max_len=soft_max)


def _pick_unique(
    items: list[str],
    limit: int,
    *,
    max_len: int = 140,
    exclude: list[str] | None = None,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    banned = list(exclude or [])
    for item in items:
        cleaned = _compress_hit(item, max_len=max_len)
        if len(cleaned) < 12:
            continue
        if re.fullmatch(r"[=_\-─—]+", cleaned):
            continue
        if not _looks_complete_phrase(cleaned):
            continue
        tail = cleaned.rsplit(" ", 1)[-1].lower().strip(".,;:…")
        if tail in _DANGLING_TAIL:
            continue
        if _is_filler(cleaned) or _is_web_residue(cleaned) or _is_math_noise(cleaned):
            continue
        if _is_heading_like_fragment(cleaned):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        if any(key[:40] == s[:40] for s in seen):
            continue
        if any(_overlap_ratio(cleaned, b) >= 0.72 for b in banned):
            continue
        if any(_overlap_ratio(cleaned, o) >= 0.72 for o in out):
            continue
        seen.add(key)
        out.append(cleaned)
        banned.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _extract_definitions_and_facts(text: str, sentences: list[str]) -> list[str]:
    facts: list[str] = []
    stop_terms = {
        "cuando", "porque", "aunque", "genera", "permite", "ayuda",
        "también", "tambien", "además", "ademas", "entonces",
    }
    for s in sentences:
        for pat in _DEF_PATTERNS:
            m = pat.search(s)
            if not m:
                continue
            term = re.sub(r"\s+", " ", m.group(1)).strip()
            gloss = m.group(2).strip().rstrip(".")
            # Solo términos cortos tipo concepto (no fragmentos de frase)
            if len(term.split()) > 5 or term.lower() in stop_terms:
                continue
            if len(term) < 3 or len(gloss) < 15:
                continue
            if not re.match(r"(?i)^[a-záéíóúñü]", term):
                continue
            facts.append(f"{term}: {_compress_hit(gloss, 100)}")
            break
    for m in _NUMBER_FACT.finditer(_clean_raw_text(text)):
        frag = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
        if 15 <= len(frag) <= 180:
            facts.append(frag)
    return _pick_unique(facts, 5, max_len=120)


def _extract_conclusions(sentences: list[str]) -> list[str]:
    """Solo cierres reales: marcadores fuertes, o suaves en el tramo final."""
    scored: list[tuple[float, str]] = []
    n = len(sentences)
    last_third = int(n * 0.66) if n else 0
    for i, s in enumerate(sentences):
        lower = s.lower()
        strong = any(k in lower for k in _CONCLUSION_STRONG)
        soft = any(k in lower for k in _CONCLUSION_SOFT)
        in_tail = bool(n and i >= last_third)
        score = 0.0
        if strong:
            score += 4.0
        elif soft and in_tail:
            score += 3.0
        elif soft and i == n - 1:
            score += 2.5
        else:
            continue
        scored.append((score + _score_key_sentence(s) * 0.15, s))
    scored.sort(key=lambda x: -x[0])
    return _pick_unique([s for _, s in scored], 3)


_BUSINESS_MARKERS = {
    "Decisiones": (
        "se decidió", "se decidio", "se acordó", "se acordo", "se aprobó",
        "se aprobo", "queda aprobado", "decisión tomada", "decision tomada",
        "se descartó", "se descarto",
    ),
    "Acciones propuestas o pendientes": (
        "acción pendiente", "accion pendiente", "próximo paso", "proximo paso",
        "queda pendiente", "responsable:", "fecha límite", "fecha limite",
        "se recomienda", "se propone", "deberá realizar", "debera realizar",
        "deben realizar", "implementar", "revisar antes",
    ),
    "Riesgos y dudas": (
        "riesgo de", "riesgo:", "riesgo ", "riesgos", "bloqueo", "dependencia crítica",
        "dependencia critica", "amenaza", "incertidumbre sobre", "retraso previsto",
        "problema crítico", "problema critico", "pendiente de confirmar",
    ),
}

# Límites teóricos / conceptos académicos ≠ riesgos operativos
_ACADEMIC_RISK_FALSE_POSITIVE = (
    "límite teórico", "limite teorico", "límites de predicción", "limites de prediccion",
    "horizonte de predicción", "horizonte de prediccion", "horizonte temporal",
    "condiciones iniciales", "efecto mariposa", "caos determinista", "exponente de",
    "imposibilit", "amplificación de errores", "amplificacion de errores",
    "predicción a largo", "prediccion a largo", "propiedad intrínseca",
    "propiedad intrinseca", "propiedad del sistema", "sistema es determinista",
    "sensibilidad a", "teoría del", "teoria del", "matemátic", "matematic",
    "error de medida", "errores de medida", "proyección meteorol", "proyeccion meteorol",
    "error creciente",
)


def _is_academic_risk_false_positive(s: str) -> bool:
    lower = s.lower()
    return any(tok in lower for tok in _ACADEMIC_RISK_FALSE_POSITIVE)


def _extract_marked_items(
    sentences: list[str],
    markers: tuple[str, ...],
    limit: int,
    *,
    reject_academic_risk: bool = False,
) -> list[str]:
    selected = []
    for s in sentences:
        lower = s.lower()
        if not any(marker in lower for marker in markers):
            continue
        if reject_academic_risk and _is_academic_risk_false_positive(s):
            continue
        selected.append(s)
    return _pick_unique(selected, limit, max_len=150)


def _format_ficha_generic(text: str, *, length: str = LENGTH_MEDIUM) -> str:
    caps = _length_caps(length)
    lines = _normalize_lines(text)
    sentences = _split_sentences(text)
    title = _guess_title(lines, text)
    title_key = title.lower().rstrip(".")

    body = [
        s
        for s in sentences
        if s.lower().rstrip(".") != title_key
        and not _is_web_residue(s)
        and not _is_math_noise(s)
        and not _is_heading_like_fragment(s)
    ]
    units = [
        unit
        for unit in _iter_content_units(text)
        if unit["text"].lower().rstrip(".") != title_key
    ]
    if not units and body:
        units = [
            {"text": sentence, "section": 0, "heading": "", "lead": i == 0}
            for i, sentence in enumerate(body)
        ]

    # En corto: solo título + resumen denso (3–5 hits totales).
    if caps["ideas_max"] <= 0 and caps["facts_max"] <= 0:
        exec_cap = min(caps["exec_max"], max(caps["exec_min"], min(5, len(body) or 1)))
        executive = _select_diverse(units, exec_cap, coverage=True)
        if len(executive) < min(2, caps["exec_min"]) and body:
            executive = _pick_unique(body, exec_cap)

        parts: list[str] = [
            title,
            "",
            _section_heading("Resumen"),
        ]
        if executive:
            parts.extend(f"- {item}" for item in executive)
        else:
            parts.append(f"- {MISSING}")
        return "\n".join(parts).strip()

    # Conclusiones primero para no mezclarlas con ideas
    conclusions = _extract_conclusions(body) if caps["conclusions_max"] else []
    decisions = (
        _extract_marked_items(body, _BUSINESS_MARKERS["Decisiones"], caps["decisions_max"])
        if caps["decisions_max"]
        else []
    )
    actions = (
        _extract_marked_items(
            body,
            _BUSINESS_MARKERS["Acciones propuestas o pendientes"],
            caps["actions_max"],
        )
        if caps["actions_max"]
        else []
    )
    risks = (
        _extract_marked_items(
            body,
            _BUSINESS_MARKERS["Riesgos y dudas"],
            caps["risks_max"],
            reject_academic_risk=True,
        )
        if caps["risks_max"]
        else []
    )
    reserved = conclusions + decisions + actions + risks

    # Resumen: frases centrales del propio texto, una idea por apartado.
    exec_target = min(
        caps["exec_max"],
        max(caps["exec_min"], min(caps["exec_max"], len(units) or 1)),
    )
    executive = _select_diverse(units, exec_target, exclude=reserved, coverage=True)
    if len(executive) < min(2, caps["exec_min"]):
        executive = _pick_unique(body, exec_target, exclude=reserved)
    if not executive and body:
        executive = _pick_unique(body, 1)

    idea_cap = min(caps["ideas_max"], max(1, len(units))) if caps["ideas_max"] else 0
    ideas = (
        _select_diverse(
            units,
            idea_cap,
            exclude=executive + reserved,
            coverage=False,
        )
        if idea_cap
        else []
    )
    if length == LENGTH_MEDIUM and len(units) <= 6 and ideas:
        ideas = ideas[: min(4, len(ideas))]

    facts = _extract_definitions_and_facts(text, body) if caps["facts_max"] else []
    facts = (
        _pick_unique(facts, caps["facts_max"], exclude=executive + ideas + reserved)
        if caps["facts_max"]
        else []
    )

    headings = _extract_section_headings(lines)
    structure = [
        h
        for h in headings
        if h.lower() != title.lower()
        and not _is_web_residue(h)
        and not _SECTION_TITLE_NOISE.match(h)
    ][: caps["structure_max"]]
    # Apartados solo si aportan estructura real (≥2)
    if len(structure) < 2 or caps["structure_max"] <= 0:
        structure = []

    conclusions = (
        _pick_unique(
            conclusions,
            caps["conclusions_max"],
            exclude=executive + ideas + decisions + actions + risks,
        )
        if caps["conclusions_max"]
        else []
    )

    parts = [title, ""]

    parts.append(_section_heading("Resumen"))
    if executive:
        parts.extend(f"- {item}" for item in executive)
    else:
        parts.append(f"- {MISSING}")
    parts.append("")

    if ideas:
        parts.append(_section_heading("Ideas / conceptos clave"))
        parts.extend(f"- {item}" for item in ideas)
        parts.append("")

    if facts:
        parts.append(_section_heading("Datos, cifras, fechas o definiciones"))
        parts.extend(f"- {item}" for item in facts)
        parts.append("")

    for section, items in (
        ("Decisiones", decisions),
        ("Acciones propuestas o pendientes", actions),
        ("Riesgos y dudas", risks),
    ):
        if items:
            parts.append(_section_heading(section))
            parts.extend(f"- {item}" for item in items)
            parts.append("")

    if structure:
        parts.append(_section_heading("Estructura / apartados"))
        parts.extend(f"- {item}" for item in structure)
        parts.append("")

    if conclusions:
        parts.append(_section_heading("Conclusiones o implicaciones"))
        parts.extend(f"- {item}" for item in conclusions)
        parts.append("")

    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Motor local — ficha de producto / electrodoméstico
# ---------------------------------------------------------------------------

_FIELD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("marca", re.compile(r"(?i)\bmarca\s*[:\-–]\s*(.+)")),
    ("modelo", re.compile(r"(?i)\bmodelo\s*[:\-–]\s*(.+)")),
    ("tipo", re.compile(r"(?i)\btipo\s*[:\-–]\s*(.+)")),
    (
        "referencia",
        re.compile(
            r"(?i)\b(?:referencia|ref\.?|n[ºo°]\s*de\s*serie|n[ºo°]\s*serie)"
            r"\s*[:\-–]\s*(.+)"
        ),
    ),
    (
        "capacidad",
        re.compile(
            r"(?i)\b(?:capacidad(?:\s+de\s*carga)?|carga\s+máxima|carga\s+maxima)"
            r"\s*[:\-–]?\s*(\d+(?:[.,]\d+)?\s*kg)\b"
        ),
    ),
    (
        "capacidad",
        re.compile(
            r"(?i)\b(\d+(?:[.,]\d+)?\s*kg)\b(?=[^.]{0,40}\b(?:capacidad|carga)\b)"
            r"|\b(?:capacidad|carga)\b[^.]{0,40}\b(\d+(?:[.,]\d+)?\s*kg)\b"
        ),
    ),
    (
        "rpm",
        re.compile(
            r"(?i)\b(?:centrifugad[oa]|velocidad(?:\s+de\s+centrifugad[oa])?|"
            r"m[aá]x(?:ima|\.)?\s*(?:velocidad|rpm))\b[^.\n]{0,40}?"
            r"(\d{3,5}\s*rpm)\b"
            r"|\b(\d{3,5}\s*rpm)\b"
        ),
    ),
    (
        "potencia",
        re.compile(
            r"(?i)\b(?:potencia|consumo(?:\s+eléctrico)?|potencia\s+(?:nominal|máxima|maxima))"
            r"\s*[:\-–]?\s*(\d+(?:[.,]\d+)?\s*(?:k?w|vatios?))\b"
        ),
    ),
    (
        "voltaje",
        re.compile(
            r"(?i)\b(?:alimentación|alimentacion|voltaje|tensión|tension|"
            r"suministro(?:\s+eléctrico)?)\s*[:\-–]?\s*"
            r"([\d.\-–]+\s*v(?:\s*/\s*\d+\s*hz)?)"
        ),
    ),
    (
        "voltaje",
        re.compile(r"(?i)\b(\d{2,3}\s*[-–]\s*\d{2,3}\s*v(?:\s*/\s*\d+\s*hz)?)\b"),
    ),
    (
        "dimensiones",
        re.compile(
            r"(?i)\bdimensiones?\s*[:\-–]?\s*"
            r"(\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*cm)"
        ),
    ),
    (
        "dimensiones",
        re.compile(
            r"(?i)\b(\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*cm)\b"
        ),
    ),
    (
        "peso",
        re.compile(r"(?i)\bpeso(?:\s+(?:neto|bruto|aprox\.?))?\s*[:\-–]?\s*(\d+(?:[.,]\d+)?\s*kg)\b"),
    ),
]

_PROGRAM_LINE = re.compile(
    r"(?i)^(?:"
    r"algod[oó]n|sint[eé]ticos?|delicado|r[aá]pido(?:\s*\d+)?|centrifugado|"
    r"lavado(?:\s+(?:r[aá]pido|eco|diario|mixto))?|eco(?:\s*\d+)?|"
    r"lana|sport|deportivo|anti[-\s]?alerg|ropa\s+de\s+cama|edred[oó]n|"
    r"camisas?|vaqueros?|jeans|mixto|diario|intensivo|prelavado|"
    r"enjuague|aclarado|drenaje|vaciado|vapor|steam|"
    r"programa\s+\d+|ciclo\s+\w+"
    r")\b.*",
)

_DURATION = re.compile(
    r"(?i)(?:(\d+)\s*h(?:oras?)?\s*(?:y\s*)?)?(\d+)\s*min(?:utos?)?"
    r"|(?:(\d+)\s*h(?:oras?)?\b)|(?:(\d+)\s*minutos?\b)",
)
_TEMP = re.compile(r"(?i)(\d{1,3})\s*°\s*c|\b(\d{1,3})\s*grados?\b")
_RPM_NUM = re.compile(r"(?i)(\d{3,5})\s*rpm\b")
_ERROR_CODE = re.compile(
    r"(?i)\b((?:Err(?:or)?|UE|OE|LE|PE|CE|dE|tE|E|F)\s*0*\d{1,2})\b"
    r"(?:\s*[:\-–—]\s*|\s+)(.{8,160}?)(?=(?:\s+(?:E|F|Err)\s*0*\d{1,2}\b)|$)",
)
_ERROR_INLINE = re.compile(
    r"(?i)\b((?:Err(?:or)?|E|F)\s*0*\d{1,2})\s*[:\-–—]\s*(.+)"
)

_CONN_KW = (
    "conexión", "conexion", "conectar", "conecte", "instal", "manguera",
    "desagüe", "desague", "agua fría", "agua fria", "agua caliente",
    "enchufe", "alargador", "ventilaci", "toma de", "grifo",
    "presión", "presion", "empot",
)
_USO_KW = (
    "cargue", "cargar", "abra la puerta", "detergente", "suavizante",
    "cajetín", "cajetin", "seleccione", "pulse", "inicio", "pausa",
    "bloqueo infantil", "panel", "tambor", "dosific", "añada",
    "sin superar", "programa y",
)
_MANT_KW = (
    "limp", "filtro", "mantenimiento", "junta", "entreabierta",
    "descalcif", "residuo", "paño", "cuidado", "revise", "retir",
    "cada mes", "periódicamente", "periodicamente",
)
_WARN_KW = (
    "no lave", "no use", "no apoye", "no toque", "no introduzca",
    "desconecte", "peligro", "advertencia", "precaución", "precaucion",
    "riesgo", "prohibido", "mantenga a los niños", "niños alejados", "nunca",
    "evitar", "no deje",
)


def _val_or_missing(value: str) -> str:
    v = (value or "").strip().rstrip(".;,")
    return v if v else MISSING


def _norm_unit(value: str, unit: str) -> str:
    v = value.strip()
    v = v.replace(",", ".")
    v = re.sub(r"\s+", " ", v)
    if unit.lower() == "rpm" and not re.search(r"(?i)rpm", v):
        v = f"{v} rpm"
    if unit.lower() == "kg" and not re.search(r"(?i)kg", v):
        v = f"{v} kg"
    v = re.sub(r"\s*[x×]\s*", " x ", v, flags=re.I)
    v = re.sub(r"(?i)\s*°\s*c", " °C", v)
    v = re.sub(r"(?i)\s*rpm\b", " rpm", v)
    v = re.sub(r"(?i)\s*kg\b", " kg", v)
    v = re.sub(r"(?i)\s*cm\b", " cm", v)
    v = re.sub(r"(?i)\s*hz\b", " Hz", v)
    v = re.sub(r"(?i)\s*v\b", " V", v)
    v = re.sub(r"(?i)\s*w\b", " W", v)
    return v.strip()


def _pick_first_group(match: re.Match[str]) -> str:
    for g in match.groups():
        if g:
            return g.strip()
    return match.group(0).strip()


def _extract_max_rpm(text: str) -> str:
    all_rpm = [int(x) for x in re.findall(r"(?i)(\d{3,5})\s*rpm\b", text)]
    if not all_rpm:
        return ""
    return _norm_unit(str(max(all_rpm)), "rpm")


def _looks_like_field_value(raw: str) -> bool:
    """Rechaza valores basura (frases largas metidas en Marca/Modelo)."""
    v = raw.strip()
    if not v or len(v) > 50:
        return False
    if v.lower() in ("no indicado", "no indicado en el texto"):
        return False
    # Demasiadas palabras → probablemente frase, no valor de campo
    if len(v.split()) > 6:
        return False
    if re.search(r"(?i)\b(escasez|economía|teoria|teoría|porque|cuando)\b", v):
        return False
    return True


def _extract_fields(text: str, data: _Extracted) -> None:
    data.rpm = _extract_max_rpm(text)
    for attr, pattern in _FIELD_PATTERNS:
        if attr == "rpm":
            continue
        current = getattr(data, attr)
        if current:
            continue
        m = pattern.search(text)
        if not m:
            continue
        raw = _pick_first_group(m)
        if attr in ("marca", "modelo", "tipo", "referencia"):
            raw = re.split(r"\s{2,}|\s+[|·]\s+", raw)[0]
            raw = raw.split("\n")[0].strip()
            # Cortar en siguiente etiqueta típica
            raw = re.split(
                r"(?i)\s+(?:marca|modelo|tipo|capacidad|dimensiones|alimentación)\s*:",
                raw,
            )[0].strip()
            if len(raw) > 60:
                raw = raw[:57] + "..."
            if not _looks_like_field_value(raw):
                continue
        if attr == "capacidad":
            raw = _norm_unit(raw, "kg")
        elif attr == "dimensiones":
            raw = _norm_unit(raw, "cm")
        elif attr == "peso":
            if data.capacidad and raw.replace(" ", "").lower() == data.capacidad.replace(" ", "").lower():
                continue
            raw = _norm_unit(raw, "kg")
        elif attr == "voltaje":
            raw = _norm_unit(raw, "V")
        elif attr == "potencia":
            raw = _norm_unit(raw, "W")
        setattr(data, attr, raw)


def _extract_capacidad_fallback(text: str, data: _Extracted) -> None:
    if data.capacidad:
        return
    m = re.search(
        r"(?i)capacidad[^.\n]{0,40}?(\d+(?:[.,]\d+)?)\s*kg"
        r"|(\d+(?:[.,]\d+)?)\s*kg[^.\n]{0,30}capacidad",
        text,
    )
    if m:
        num = m.group(1) or m.group(2)
        data.capacidad = _norm_unit(f"{num} kg", "kg")


def _parse_duration(text: str) -> str:
    m = _DURATION.search(text)
    if not m:
        return ""
    h = m.group(1) or m.group(3)
    mins = m.group(2) or m.group(4)
    if h and mins:
        return f"{int(h)} h {int(mins)} min"
    if h:
        return f"{int(h)} h"
    if mins:
        return f"{int(mins)} min"
    return ""


def _format_program(line: str) -> str | None:
    cleaned = line.strip()
    if len(cleaned) < 6:
        return None
    lower = cleaned.lower()
    if lower in ("programas", "programas principales", "ciclos", "programas de lavado"):
        return None

    name = cleaned
    rest = ""
    for sep in (" — ", " – ", " - ", ": ", " —", "–"):
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            name, rest = parts[0].strip(), parts[1].strip()
            break

    temp_m = _TEMP.search(cleaned)
    rpm_m = _RPM_NUM.search(cleaned)
    dur = _parse_duration(cleaned)

    name_clean = re.sub(r"(?i)\s*\d{1,3}\s*°\s*c", "", name).strip()
    name_clean = re.sub(r"\s{2,}", " ", name_clean)

    bits: list[str] = []
    if rest:
        desc = rest
        desc = _TEMP.sub("", desc)
        desc = _RPM_NUM.sub("", desc)
        desc = _DURATION.sub("", desc)
        desc = re.sub(r"\s*[,;]\s*", ", ", desc)
        desc = re.sub(r"(?:,\s*)+$", "", desc)
        desc = re.sub(r"\s{2,}", " ", desc).strip(" ,;—–-.")
        desc = re.sub(r"(?i)\s+\ba\b\s*$", "", desc).strip(" ,;—–-.")
        if desc:
            bits.append(desc)

    details: list[str] = []
    if temp_m:
        t = temp_m.group(1) or temp_m.group(2)
        details.append(f"{t} °C")
    if rpm_m:
        details.append(f"{int(rpm_m.group(1))} rpm")
    if dur:
        details.append(dur)

    out = name_clean
    if bits:
        out += f" — {bits[0]}"
    if details:
        out += f" ({', '.join(details)})"
    return out


def _extract_programs(lines: list[str], text: str, data: _Extracted) -> None:
    seen: set[str] = set()
    in_program_section = False
    for line in lines:
        lower = line.lower()
        if re.match(r"(?i)^programas?\b|^ciclos?\b", lower):
            in_program_section = True
            continue
        if re.match(
            r"(?i)^(uso diario|mantenimiento|aver[ií]as|advertencias|"
            r"instalaci[oó]n|conexi[oó]n|especificaciones)\b",
            lower,
        ):
            in_program_section = False

        is_prog = bool(_PROGRAM_LINE.match(line)) or (
            in_program_section
            and len(line) > 8
            and not re.match(r"(?i)^(marca|modelo|capacidad)\b", line)
        )
        if not is_prog:
            continue
        formatted = _format_program(line)
        if not formatted:
            continue
        key = formatted.lower()
        if key in seen:
            continue
        seen.add(key)
        data.programas.append(formatted)


def _error_sort_key(item: str) -> tuple:
    m = re.match(r"(?i)^([A-Za-z]+)\s*0*(\d+)", item)
    if not m:
        return (99, 9999, item)
    letter = m.group(1).upper()
    num = int(m.group(2))
    order = {"E": 0, "F": 1, "ERR": 2, "ERROR": 2}.get(letter, 10)
    return (order, num, item)


def _extract_errors(lines: list[str], text: str, data: _Extracted) -> None:
    seen: set[str] = set()
    for line in lines:
        m = _ERROR_INLINE.match(line)
        if m:
            code = re.sub(r"\s+", "", m.group(1).upper())
            code = re.sub(r"(?i)^(E|F|ERR|ERROR)0+(\d)$", r"\1\2", code)
            desc = m.group(2).strip().rstrip(".")
            key = code.lower()
            if key not in seen:
                seen.add(key)
                data.errores.append(f"{code} — {desc}")
            continue

        for em in _ERROR_CODE.finditer(line):
            code = re.sub(r"\s+", "", em.group(1).upper())
            code = re.sub(r"(?i)^(E|F|ERR|ERROR)0+(\d)$", r"\1\2", code)
            desc = em.group(2).strip().rstrip(".")
            if len(desc) < 5:
                continue
            key = code.lower()
            if key not in seen:
                seen.add(key)
                data.errores.append(f"{code} — {desc}")

    data.errores = sorted(data.errores, key=_error_sort_key)


def _is_useful_bullet(line: str) -> bool:
    if len(line) < 15:
        return False
    if _TOC_NOISE.match(line):
        return False
    if re.fullmatch(
        r"(?i)(identificaci[oó]n|especificaciones|conexi[oó]n.*|"
        r"programas?.*|uso diario|mantenimiento|aver[ií]as.*|"
        r"advertencias?.*|instalaci[oó]n.*|manual de usuario.*)",
        line,
    ):
        return False
    return True


def _classify_bullet(line: str) -> str | None:
    lower = line.lower()
    if _ERROR_INLINE.match(line) or _ERROR_CODE.search(line):
        return None
    if _PROGRAM_LINE.match(line):
        return None

    warn_score = sum(1 for k in _WARN_KW if k in lower)
    conn_score = sum(1 for k in _CONN_KW if k in lower)
    uso_score = sum(1 for k in _USO_KW if k in lower)
    mant_score = sum(1 for k in _MANT_KW if k in lower)

    scores = {
        "advertencias": warn_score,
        "conexion": conn_score,
        "mantenimiento": mant_score,
        "uso": uso_score,
    }
    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        return None
    if warn_score and warn_score >= scores[best]:
        return "advertencias"
    if mant_score and mant_score >= uso_score and mant_score >= conn_score:
        if mant_score >= scores[best]:
            return "mantenimiento"
    return best


def _add_unique(bucket: list[str], line: str, limit: int = 6) -> None:
    key = line.lower().strip()
    if any(key == b.lower().strip() for b in bucket):
        return
    if len(bucket) >= limit:
        return
    # Viñetas densas: acortar relleno extremo
    if len(line) > 160:
        line = _compress_hit(line, max_len=140)
        if not line:
            return
    bucket.append(line)


def _extract_all(
    text: str,
    *,
    bullet_limit: int = 6,
    program_limit: int = 10,
) -> _Extracted:
    data = _Extracted()
    lines = _normalize_lines(text)

    _extract_fields(text, data)
    _extract_capacidad_fallback(text, data)

    if not data.modelo:
        m = re.search(
            r"(?i)(?:lavadora|secadora|lavavajillas|horno|frigor[ií]fico)"
            r"\s+([A-Za-z0-9][\w\- ]{1,40})",
            text,
        )
        if m:
            cand = m.group(1).strip()
            cand = re.split(r"\s{2,}|$", cand)[0]
            if _looks_like_field_value(cand):
                data.modelo = cand

    _extract_programs(lines, text, data)
    if program_limit and len(data.programas) > program_limit:
        data.programas = data.programas[:program_limit]
    _extract_errors(lines, text, data)

    for line in lines:
        if not _is_useful_bullet(line):
            continue
        if re.match(
            r"(?i)^(marca|modelo|capacidad|tipo|dimensiones|alimentaci[oó]n|peso)\s*:",
            line,
        ):
            continue
        section = _classify_bullet(line)
        if section == "conexion":
            _add_unique(data.conexion, line, limit=bullet_limit)
        elif section == "uso":
            _add_unique(data.uso, line, limit=bullet_limit)
        elif section == "mantenimiento":
            _add_unique(data.mantenimiento, line, limit=bullet_limit)
        elif section == "advertencias":
            _add_unique(data.advertencias, line, limit=bullet_limit)

    return data


def _section_heading(name: str) -> str:
    """Nombre de sección solo, sin rayas ni almohadillas."""
    return name.strip()


def _bullet(label: str, value: str) -> str:
    return f"- {label}: {_val_or_missing(value)}"


def _section_bullets(items: list[str]) -> list[str]:
    if not items:
        return [f"- {MISSING}"]
    return [f"- {item}" for item in items]


def _format_ficha_product(data: _Extracted) -> str:
    parts: list[str] = []

    product_name = " ".join(
        part for part in (data.marca.strip(), data.modelo.strip()) if part
    )
    if product_name:
        parts.append(product_name)
        parts.append("")

    parts.append(_section_heading("Identificación"))
    parts.append(_bullet("Marca", data.marca))
    parts.append(_bullet("Modelo", data.modelo))
    parts.append(_bullet("Tipo", data.tipo))
    if data.referencia:
        parts.append(_bullet("Referencia / serie", data.referencia))
    parts.append("")

    parts.append(_section_heading("Especificaciones"))
    parts.append(_bullet("Capacidad", data.capacidad))
    parts.append(_bullet("Velocidad de centrifugado", data.rpm))
    parts.append(_bullet("Potencia", data.potencia))
    parts.append(_bullet("Voltaje", data.voltaje))
    parts.append(_bullet("Dimensiones", data.dimensiones))
    parts.append(_bullet("Peso", data.peso))
    parts.append("")

    parts.append(_section_heading("Conexión / instalación"))
    parts.extend(_section_bullets(data.conexion))
    parts.append("")

    parts.append(_section_heading("Programas"))
    parts.extend(_section_bullets(data.programas))
    parts.append("")

    parts.append(_section_heading("Uso diario"))
    parts.extend(_section_bullets(data.uso))
    parts.append("")

    parts.append(_section_heading("Mantenimiento"))
    parts.extend(_section_bullets(data.mantenimiento))
    parts.append("")

    parts.append(_section_heading("Códigos de error / averías"))
    parts.extend(_section_bullets(data.errores))
    parts.append("")

    parts.append(_section_heading("Advertencias importantes"))
    parts.extend(_section_bullets(data.advertencias))
    parts.append("")

    return "\n".join(parts).strip()
