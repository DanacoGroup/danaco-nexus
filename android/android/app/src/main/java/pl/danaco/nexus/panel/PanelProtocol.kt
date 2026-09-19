package pl.danaco.nexus.panel

import org.json.JSONException
import org.json.JSONObject

/** Kontekst przekazywany do panelu (`nexus:context`): strona albo ekran telefonu. */
data class PanelContext(
    val kind: String,
    val title: String,
    val url: String = "",
    val text: String = "",
    /** Obraz jako `data:image/jpeg;base64,…` (zrzut ekranu) albo `null`. */
    val image: String? = null,
)

/** Zdarzenia od panelu do rodzica (umowa trybu osadzonego). */
sealed interface PanelEvent {
    data object Ready : PanelEvent

    data class Insert(val text: String) : PanelEvent

    data class Copy(val text: String) : PanelEvent
}

/**
 * Umowa trybu osadzonego (`/?widok=panel`): rodzic → panel `nexus:auth`, `nexus:context`, `nexus:prompt`;
 * panel → rodzic `nexus:ready`, `nexus:insert`, `nexus:copy`. W WebView panel jest oknem najwyższego
 * poziomu, więc komunikaty „do rodzica” trafiają do tego samego okna i odbiera je wstrzyknięty skrypt.
 */
object PanelProtocol {
    const val MAX_TEXT = 20_000
    private const val MAX_EVENT_TEXT = 100_000

    fun auth(token: String): String = JSONObject().put("type", "nexus:auth").put("token", token).toString()

    fun context(context: PanelContext): String {
        val body = JSONObject()
            .put("kind", if (context.kind == "screen") "screen" else "page")
            .put("title", context.title.take(300))
            .put("url", context.url.take(2000))
            .put("text", context.text.take(MAX_TEXT))
        if (context.image != null) body.put("image", context.image)
        return JSONObject().put("type", "nexus:context").put("context", body).toString()
    }

    fun prompt(text: String, send: Boolean): String =
        JSONObject().put("type", "nexus:prompt").put("text", text).put("send", send).toString()

    /** Kod JS wysyłający wiadomość do strony panelu. */
    fun script(message: String): String = "window.postMessage($message, window.location.origin);"

    fun parse(raw: String?): PanelEvent? {
        if (raw == null || raw.length > MAX_EVENT_TEXT + 200) return null
        val json = try {
            JSONObject(raw)
        } catch (_: JSONException) {
            return null
        }
        val text = json.optString("text", "").take(MAX_EVENT_TEXT)
        return when (json.optString("type")) {
            "nexus:ready" -> PanelEvent.Ready
            "nexus:insert" -> if (text.isNotBlank()) PanelEvent.Insert(text) else null
            "nexus:copy" -> if (text.isNotBlank()) PanelEvent.Copy(text) else null
            else -> null
        }
    }
}
