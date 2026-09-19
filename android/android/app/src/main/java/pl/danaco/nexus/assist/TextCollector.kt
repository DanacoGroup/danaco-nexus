package pl.danaco.nexus.assist

/**
 * Zbieranie tekstu widocznego na ekranie (struktura asystenta, usługa dostępności): bez pustych
 * i powtórzonych fragmentów, z limitem długości. Czysta klasa – testowana jednostkowo.
 */
class TextCollector(private val limit: Int = 12_000) {
    private val seen = HashSet<String>()
    private val parts = ArrayList<String>()
    private var length = 0

    val full: Boolean get() = length >= limit

    fun add(raw: CharSequence?) {
        if (raw == null || full) return
        val text = WHITESPACE.replace(raw.toString(), " ").trim()
        if (text.isEmpty() || !seen.add(text)) return
        val room = limit - length
        val piece = if (text.length > room) text.take(room).trimEnd() + "…" else text
        parts += piece
        length += piece.length + 1
    }

    fun text(): String = parts.joinToString("\n")

    private companion object {
        val WHITESPACE = Regex("\\s+")
    }
}
