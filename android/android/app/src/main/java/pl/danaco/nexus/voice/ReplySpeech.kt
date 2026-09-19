package pl.danaco.nexus.voice

/**
 * Tekst odpowiedzi strumieniowanej zdarzeniami `text.delta`/`text.block` zamieniany na kolejne
 * fragmenty do przeczytania (jak `replyText` w trybie rozmowy przeglądarki).
 */
class ReplySpeech {
    private val text = StringBuilder()
    private var cursor = 0

    /** Czy przyszedł już jakikolwiek tekst odpowiedzi. */
    var received = false
        private set

    fun onDelta(delta: String): List<String> {
        if (delta.isEmpty()) return emptyList()
        text.append(delta)
        received = true
        return take(false)
    }

    /** Nowy blok tekstu (np. po wywołaniu narzędzia) – granica zdania. */
    fun onBlock() {
        if (text.isNotEmpty() && !text.endsWith("\n")) text.append("\n\n")
    }

    /** Koniec odpowiedzi – reszta tekstu. */
    fun finish(): List<String> = take(true)

    private fun take(final: Boolean): List<String> {
        val result = Sentences.take(Sentences.speakable(text.toString()), cursor, final)
        cursor = result.next
        return result.chunks
    }
}
