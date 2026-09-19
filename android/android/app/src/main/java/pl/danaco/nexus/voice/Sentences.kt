package pl.danaco.nexus.voice

/**
 * Podział strumieniowanej odpowiedzi na zdania do przeczytania – port `frontend/src/voice/sentences.ts`
 * (te same reguły i progi, żeby mowa w aplikacji brzmiała tak samo jak w przeglądarce).
 */
object Sentences {
    private val boundary = Regex("[.!?…](?=[\"'”)\\]]?(\\s|\\z))|\\n+")
    private val firstBoundary = Regex("[,;:–—](?=\\s)")
    private const val MIN_CHUNK = 24
    private const val FIRST_MIN = 30

    data class Result(val chunks: List<String>, val next: Int)

    /**
     * Gotowe do przeczytania fragmenty tekstu od pozycji [from]. Bez [final] ostatni, niedokończony
     * fragment czeka na dalszy tekst; krótkie zdania są łączone.
     */
    fun take(text: String, from: Int, final: Boolean): Result {
        if (from == 0 && !final) {
            val early = firstClause(text)
            if (early != null) {
                val rest = take(text, early.second, false)
                return Result(listOf(early.first) + rest.chunks, rest.next)
            }
        }
        val chunks = mutableListOf<String>()
        var start = from.coerceIn(0, text.length)
        val pending = StringBuilder()
        var match = boundary.find(text, start)
        while (match != null) {
            val end = match.range.last + 1
            pending.append(text, start, end)
            start = end
            if (pending.trim().length >= MIN_CHUNK) {
                chunks += pending.trim().toString()
                pending.clear()
            }
            match = if (end < text.length) boundary.find(text, end) else null
        }
        if (final) {
            pending.append(text, start, text.length)
            if (pending.isNotBlank()) chunks += pending.trim().toString()
            return Result(chunks, text.length)
        }
        return Result(chunks, start - pending.length)
    }

    /** Tekst odpowiedzi do czytania: bez bloków kodu i znaczników Markdown. */
    fun speakable(text: String): String =
        text
            .replace(Regex("```[\\s\\S]*?(```|\\z)"), " ")
            .replace(Regex("!\\[[^\\]]*]\\([^)]*\\)"), " ")
            .replace(Regex("\\[([^\\]]*)]\\([^)]*\\)"), "$1")
            .replace(Regex("[*_`#>|]"), " ")

    private fun firstClause(text: String): Pair<String, Int>? {
        if (text.length <= FIRST_MIN) return null
        val sentenceEnd = boundary.find(text, 0)
        val clause = firstBoundary.find(text, FIRST_MIN) ?: return null
        if (sentenceEnd != null && sentenceEnd.range.first <= clause.range.first) return null
        val next = clause.range.last + 1
        return text.substring(0, next).trim() to next
    }
}
