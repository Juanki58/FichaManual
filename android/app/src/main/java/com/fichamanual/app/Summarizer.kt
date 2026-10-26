package com.fichamanual.app

/**
 * Motor local simplificado (ficha genérica), alineado con la idea del summarizer
 * de escritorio: síntesis corta en español, sin API ni servidor.
 */
object Summarizer {

    private const val MISSING = "No indicado en el texto"

    private val fillerStarts = listOf(
        "es importante destacar", "cabe señalar", "cabe destacar",
        "es necesario", "como es sabido", "en este sentido",
        "de hecho", "por otro lado", "por otra parte",
        "así mismo", "asimismo", "en primer lugar", "en segundo lugar",
        "vale la pena", "resulta evidente", "es evidente que",
    )

    private val conclusionStrong = listOf(
        "en conclusión", "en conclusion", "en resumen", "en definitiva",
        "se concluye", "como resultado", "para concluir",
        "a modo de conclusión", "a modo de conclusion",
    )

    private val conclusionSoft = listOf(
        "por tanto", "por lo tanto", "así pues", "asi pues",
        "implica", "implicación", "implicacion", "consecuencia", "finalmente",
    )

    fun summarize(text: String): String {
        val cleaned = text.trim()
        if (cleaned.isEmpty()) return "No hay texto para resumir."

        val lines = normalizeLines(cleaned)
        val sentences = splitSentences(cleaned)
        val title = guessTitle(lines, sentences)
        val titleKey = title.lowercase().trimEnd('.')
        val body = sentences.filter { it.lowercase().trimEnd('.') != titleKey }

        val conclusions = extractConclusions(body)
        val executive = pickExecutive(body, conclusions)
        val ideas = pickUnique(
            body.sortedByDescending { scoreKeySentence(it) },
            8,
            exclude = executive + conclusions,
        ).let { if (body.size <= 6) it.take(4) else it }
        val facts = extractFacts(cleaned, sentences)
            .let { pickUnique(it, 5, exclude = executive + ideas + conclusions) }
        val structure = extractHeadings(lines)
            .filter { it.lowercase() != title.lowercase() }
            .take(6)
            .let { if (it.size < 2) emptyList() else it }
        val finalConclusions = pickUnique(conclusions, 3, exclude = executive + ideas)

        return buildString {
            appendLine("── Título / tema ──")
            appendLine("- $title")
            appendLine()
            appendLine("── Resumen ──")
            if (executive.isEmpty()) appendLine("- $MISSING")
            else executive.forEach { appendLine("- $it") }
            appendLine()
            appendLine("── Ideas / conceptos clave ──")
            if (ideas.isEmpty()) appendLine("- $MISSING")
            else ideas.forEach { appendLine("- $it") }
            appendLine()
            if (facts.isNotEmpty()) {
                appendLine("── Datos, cifras o definiciones ──")
                facts.forEach { appendLine("- $it") }
                appendLine()
            }
            if (structure.isNotEmpty()) {
                appendLine("── Estructura / apartados ──")
                structure.forEach { appendLine("- $it") }
                appendLine()
            }
            if (finalConclusions.isNotEmpty()) {
                appendLine("── Conclusiones o implicaciones ──")
                finalConclusions.forEach { appendLine("- $it") }
                appendLine()
            }
            append("Motor: local Android (ficha genérica). Caracteres leídos: ${cleaned.length}.")
        }.trim()
    }

    private fun normalizeLines(text: String): List<String> {
        return text.replace("\r\n", "\n").replace('\r', '\n')
            .lineSequence()
            .map { it.replace(Regex("\\s+"), " ").trim(' ', '\u2022', '*', '-', '\u2013', '\u2014', '\t', '#') }
            .filter { it.length >= 3 }
            .filterNot { it.matches(Regex("[=_\\-]{3,}")) }
            .filterNot { it.matches(Regex("(?i)^(índice|indice|tabla de contenidos|contenido|sumario|capítulo|capitulo|página|pagina).*")) }
            .map { if (it.length > 320) it.take(317) + "..." else it }
            .toList()
    }

    private fun cleanRaw(text: String): String {
        return text.replace("\r\n", "\n").replace('\r', '\n')
            .lineSequence()
            .map { line ->
                val s = line.trim()
                if (s.matches(Regex("[=_\\-─—]{3,}"))) ""
                else s.replace(Regex("\\s*[=_\\-─—]{3,}\\s*$"), "")
            }
            .joinToString("\n")
    }

    private fun splitSentences(text: String): List<String> {
        val out = mutableListOf<String>()
        for (para in cleanRaw(text).split(Regex("\\n\\s*\\n+"))) {
            var chunk = para.replace(Regex("\\s+"), " ").trim()
            chunk = chunk.replace(Regex("\\s*[=_\\-─—]{3,}\\s*"), " ").trim()
            if (chunk.length < 20) {
                if (chunk.length >= 8 && !chunk.matches(Regex("[=_\\-─—]+"))) out += chunk
                continue
            }
            val parts = chunk.split(Regex("(?<=[.!?…])\\s+(?=[A-ZÁÉÍÓÚÑÜ¿¡\"'])"))
            for (p in parts) {
                var s = p.trim().replace(Regex("\\s*[=_\\-─—]{3,}\\s*"), " ").trim()
                if (s.length >= 20 || (s.length >= 12 && s !in out)) out += s
            }
        }
        return out
    }

    private fun isHeading(line: String): Boolean {
        val s = line.trim()
        if (s.length !in 4..90 || s.endsWith(".")) return false
        val words = s.split(Regex("\\s+"))
        if (words.size > 12) return false
        if (s == s.uppercase() && words.size <= 10) return true
        if (words.size <= 8 && !Regex("\\d{2,}").containsMatchIn(s)) {
            val lower = s.lowercase()
            if (listOf(" que ", " porque ", " cuando ", " donde ").any { it in lower }) return false
            return true
        }
        return false
    }

    private fun guessTitle(lines: List<String>, sentences: List<String>): String {
        for (line in lines.take(8)) {
            val lower = line.lowercase()
            if (lower.startsWith("marca:") || lower.startsWith("modelo:") || lower.startsWith("capacidad:")) continue
            if (Regex("[=_\\-─—]{3,}").containsMatchIn(line)) continue
            if (isHeading(line)) return line.trim().trimEnd('.')
        }
        val first = sentences.firstOrNull() ?: return "Texto sin título explícito"
        return if (first.length <= 100) first.trimEnd('.') else first.take(97).trimEnd() + "..."
    }

    private fun extractHeadings(lines: List<String>): List<String> {
        val seen = mutableSetOf<String>()
        val out = mutableListOf<String>()
        for (line in lines) {
            if (!isHeading(line) || line.split(Regex("\\s+")).size > 8 || line.length > 70) continue
            val key = line.lowercase()
            if (key in seen) continue
            seen += key
            out += line
            if (out.size >= 10) break
        }
        return out
    }

    private fun scoreKeySentence(s: String): Double {
        val lower = s.lowercase()
        var score = 0.0
        if (listOf(
                "se define", "consiste en", "significa", "es la", "es el",
                "concepto", "teoría", "teoria", "principio", "ley de",
                "implica", "por tanto", "por lo tanto", "escasez", "recursos",
            ).any { it in lower }
        ) score += 2.0
        if (Regex("\\d").containsMatchIn(s)) score += 1.0
        if ((conclusionStrong + conclusionSoft).any { it in lower }) score += 1.5
        val n = s.length
        when {
            n in 40..220 -> score += 1.0
            n > 280 -> score -= 0.5
        }
        return score
    }

    private fun tokenSet(s: String): Set<String> =
        Regex("[a-záéíóúñü0-9]{3,}").findAll(s.lowercase()).map { it.value }.toSet()

    private fun overlapRatio(a: String, b: String): Double {
        val ta = tokenSet(a)
        val tb = tokenSet(b)
        if (ta.isEmpty() || tb.isEmpty()) return 0.0
        return ta.intersect(tb).size.toDouble() / minOf(ta.size, tb.size).coerceAtLeast(1)
    }

    private fun isFiller(s: String): Boolean {
        val lower = s.lowercase().trim()
        if (fillerStarts.any { lower.startsWith(it) }) return true
        if (tokenSet(lower).size < 3 && !Regex("\\d").containsMatchIn(lower)) return true
        return false
    }

    private fun compressHit(s: String, maxLen: Int = 140): String {
        var cleaned = s.replace(Regex("\\s+"), " ").trim().trimEnd('.')
        cleaned = cleaned.replace(Regex("\\s*[=_\\-─—]{3,}\\s*"), " ").trim()
        val lower = cleaned.lowercase()
        for (f in fillerStarts) {
            if (lower.startsWith(f)) {
                cleaned = cleaned.drop(f.length).trimStart(' ', ',', ':', ';', '¿', '¡', '-')
                if (cleaned.isNotEmpty()) cleaned = cleaned.replaceFirstChar { it.uppercase() }
                break
            }
        }
        if (cleaned.length <= maxLen) return cleaned
        val cut = cleaned.take(maxLen + 1)
        for (sep in listOf("; ", ": ", " — ", " – ", ", ")) {
            val idx = cut.lastIndexOf(sep)
            if (idx >= maxLen / 2) return cut.take(idx).trimEnd(' ', ',', ';', ':')
        }
        val sp = cut.lastIndexOf(' ')
        return if (sp >= maxLen / 2) cut.take(sp).trimEnd(' ', ',', ';', ':') + "…"
        else cut.take(maxLen - 1).trimEnd() + "…"
    }

    private fun pickUnique(
        items: List<String>,
        limit: Int,
        maxLen: Int = 140,
        exclude: List<String> = emptyList(),
    ): List<String> {
        val out = mutableListOf<String>()
        val seen = mutableSetOf<String>()
        val banned = exclude.toMutableList()
        for (item in items) {
            val cleaned = compressHit(item, maxLen)
            if (cleaned.length < 12 || cleaned.matches(Regex("[=_\\-─—]+")) || isFiller(cleaned)) continue
            val key = cleaned.lowercase()
            if (key in seen || seen.any { it.take(40) == key.take(40) }) continue
            if (banned.any { overlapRatio(cleaned, it) >= 0.72 }) continue
            if (out.any { overlapRatio(cleaned, it) >= 0.72 }) continue
            seen += key
            out += cleaned
            banned += cleaned
            if (out.size >= limit) break
        }
        return out
    }

    private fun pickExecutive(body: List<String>, conclusions: List<String>): List<String> {
        val target = when {
            body.size >= 4 -> 4
            else -> maxOf(3, minOf(5, body.size))
        }
        val scored = body.mapIndexed { i, s ->
            val pos = maxOf(0.0, 1.5 - i * 0.15)
            val pen = if (conclusions.any { overlapRatio(s, it) >= 0.72 }) -2.0 else 0.0
            Triple(scoreKeySentence(s) + pos + pen, i, s)
        }.sortedWith(compareByDescending<Triple<Double, Int, String>> { it.first }.thenBy { it.second })
        val topIdx = scored.take(maxOf(target + 2, 5)).map { it.second }.toSortedSet()
        val pool = topIdx.mapNotNull { body.getOrNull(it) }
        var exec = pickUnique(pool, minOf(5, maxOf(3, target)), exclude = conclusions)
        if (exec.size < 2) exec = pickUnique(body, 3, exclude = conclusions)
        return exec
    }

    private fun extractConclusions(sentences: List<String>): List<String> {
        val n = sentences.size
        val lastThird = if (n == 0) 0 else (n * 0.66).toInt()
        val scored = mutableListOf<Pair<Double, String>>()
        sentences.forEachIndexed { i, s ->
            val lower = s.lowercase()
            val strong = conclusionStrong.any { it in lower }
            val soft = conclusionSoft.any { it in lower }
            val inTail = n > 0 && i >= lastThird
            val score = when {
                strong -> 4.0
                soft && inTail -> 3.0
                soft && i == n - 1 -> 2.5
                else -> return@forEachIndexed
            }
            scored += (score + scoreKeySentence(s) * 0.15) to s
        }
        return pickUnique(scored.sortedByDescending { it.first }.map { it.second }, 3)
    }

    private fun extractFacts(text: String, sentences: List<String>): List<String> {
        val facts = mutableListOf<String>()
        val stop = setOf("cuando", "porque", "aunque", "genera", "permite", "ayuda", "también", "tambien", "además", "ademas", "entonces")
        val defPatterns = listOf(
            Regex("(?i)\\b([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\\w\\-áéíóúñü]{3,40})\\s+es\\s+(el concepto\\b.+)"),
            Regex("(?i)\\b([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\\w\\-áéíóúñü]{3,40})\\s+(?:se define como|consiste en|significa|denota)\\s+(.+)"),
            Regex("(?i)^([A-ZÁÉÍÓÚÑÜa-záéíóúñü][\\w\\-áéíóúñü\\s]{2,40}?)\\s*:\\s*(.{20,200})$"),
        )
        for (s in sentences) {
            for (pat in defPatterns) {
                val m = pat.find(s) ?: continue
                val term = m.groupValues[1].replace(Regex("\\s+"), " ").trim()
                val gloss = m.groupValues[2].trim().trimEnd('.')
                if (term.split(Regex("\\s+")).size > 5 || term.lowercase() in stop) continue
                if (term.length < 3 || gloss.length < 15) continue
                if (!Regex("(?i)^[a-záéíóúñü]").containsMatchIn(term)) continue
                facts += "$term: ${compressHit(gloss, 100)}"
                break
            }
        }
        val numberFact = Regex(
            "(?i)(?:^|[.\\n]\\s*)([^.!?\\n]{10,220}?(?:\\d+(?:[.,]\\d+)?\\s*%|" +
                "\\d+(?:[.,]\\d+)?\\s*(?:millones?|mil|billones?)|" +
                "(?:siglo|año|años)\\s+\\d{2,4}|\\d{4})[^.!?\\n]{0,120})"
        )
        for (m in numberFact.findAll(cleanRaw(text))) {
            val frag = m.groupValues[1].replace(Regex("\\s+"), " ").trim().trimEnd('.')
            if (frag.length in 15..180) facts += frag
        }
        return pickUnique(facts, 5, maxLen = 120)
    }
}
