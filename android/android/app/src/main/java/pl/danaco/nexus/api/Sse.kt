package pl.danaco.nexus.api

/** Zdarzenie strumienia Server-Sent Events. */
data class SseEvent(val id: String?, val event: String, val data: String)

/**
 * Przyrostowy parser SSE (format `/api/runs/<id>/events`): pola `id`, `event`, `data`
 * (wiele linii łączonych znakiem nowej linii), komentarze `:`; pusta linia kończy zdarzenie.
 */
class SseParser {
    private var id: String? = null
    private var event: String? = null
    private val data = StringBuilder()
    private var hasData = false

    /** Identyfikator ostatniego zdarzenia (do wznowienia przez `Last-Event-ID`). */
    var lastEventId: String? = null
        private set

    /** Przetwarza jedną linię (bez znaku końca linii); zwraca zdarzenie po pustej linii. */
    fun feed(line: String): SseEvent? {
        if (line.isEmpty()) return dispatch()
        if (line.startsWith(":")) return null
        val colon = line.indexOf(':')
        val field = if (colon < 0) line else line.substring(0, colon)
        var value = if (colon < 0) "" else line.substring(colon + 1)
        if (value.startsWith(" ")) value = value.substring(1)
        when (field) {
            "id" -> id = value
            "event" -> event = value
            "data" -> {
                if (hasData) data.append('\n')
                data.append(value)
                hasData = true
            }
        }
        return null
    }

    private fun dispatch(): SseEvent? {
        val result =
            if (hasData) SseEvent(id, event ?: "message", data.toString()) else null
        if (id != null) lastEventId = id
        id = null
        event = null
        data.clear()
        hasData = false
        return result
    }
}
