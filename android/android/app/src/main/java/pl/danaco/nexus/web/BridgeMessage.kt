package pl.danaco.nexus.web

import org.json.JSONException
import org.json.JSONObject
import pl.danaco.nexus.config.DeviceKeyStore

/** Wiadomości od mostka w oknie aplikacji (`assets/nexus/most.js`). Treść strony to dane – walidowane. */
sealed interface BridgeMessage {
    data class Hello(val path: String) : BridgeMessage

    data class KeyCreated(val token: String, val id: String) : BridgeMessage

    data object KeyNoLogin : BridgeMessage

    data class KeyError(val status: Int) : BridgeMessage

    data class RunStarted(val runId: String, val conversationId: String) : BridgeMessage

    data class VoiceStart(val conversationId: String?) : BridgeMessage

    data object OpenSettings : BridgeMessage

    data object OpenSms : BridgeMessage

    companion object {
        private val UUID = Regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

        fun isUuid(value: String?): Boolean = value != null && UUID.matches(value)

        /** Parsuje wiadomość; nieznane lub niepoprawne – `null`. */
        fun parse(raw: String?): BridgeMessage? {
            if (raw == null || raw.length > 16_384) return null
            val json = try {
                JSONObject(raw)
            } catch (_: JSONException) {
                return null
            }
            return when (json.optString("type")) {
                "hello" -> Hello(json.optString("path").take(200))
                "key.created" -> {
                    val token = json.optString("token")
                    if (DeviceKeyStore.isValidToken(token)) KeyCreated(token, json.optString("id").take(64)) else null
                }
                "key.nologin" -> KeyNoLogin
                "key.error" -> KeyError(json.optInt("status", 0))
                "run.started" -> {
                    val run = json.optString("runId")
                    val conversation = json.optString("conversationId")
                    if (isUuid(run) && isUuid(conversation)) RunStarted(run, conversation) else null
                }
                "voice.start" -> VoiceStart(json.optString("conversationId").takeIf { isUuid(it) })
                "settings.open" -> OpenSettings
                "sms.open" -> OpenSms
                else -> null
            }
        }

        /** Prośba do strony o utworzenie klucza urządzenia o podanej nazwie. */
        fun keyRequest(deviceName: String): String =
            JSONObject().put("type", "key.request").put("name", deviceName.take(100)).toString()
    }
}
