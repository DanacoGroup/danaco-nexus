package pl.danaco.nexus.api

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** Błąd odpowiedzi API z kodem HTTP i komunikatem serwera (pole `detail`). */
class ApiException(val status: Int, message: String) : IOException(message) {
    val unauthorized: Boolean get() = status == 401
}

data class Voice(val id: String, val name: String)

data class VoiceConfig(val available: Boolean, val voices: List<Voice>, val defaultVoice: String)

data class ConversationSummary(val id: String, val title: String, val active: Boolean)

class SpeechAudio(val bytes: ByteArray, val mime: String)

data class RunStatus(val id: String, val status: String, val conversationId: String, val error: String) {
    val active: Boolean get() = status == "queued" || status == "running"
}

/** Zdarzenie zadania agenta (`text.delta`, `run.completed`…) z danymi JSON. */
data class RunEvent(val id: Long, val type: String, val data: JSONObject) {
    val final: Boolean get() = type in FINAL_EVENTS
    val text: String get() = data.optString("text", "")

    companion object {
        val FINAL_EVENTS = setOf("run.completed", "run.failed", "run.cancelled")
    }
}

/**
 * Klient API Nexusa dla modułów natywnych. Uwierzytelnienie kluczem urządzenia
 * (`Authorization: Bearer nxd_…`) – bez ciasteczek i bez nagłówka CSRF.
 */
class NexusApi(
    baseUrl: String,
    private val token: () -> String?,
    client: OkHttpClient = defaultClient(),
) {
    private val base: HttpUrl = baseUrl.trimEnd('/').toHttpUrl()
    private val http = client
    private val stream = client.newBuilder().readTimeout(STREAM_READ_TIMEOUT_S, TimeUnit.SECONDS).build()

    suspend fun me(): String = json(get("api/auth/me")).optString("username", "")

    suspend fun voiceConfig(): VoiceConfig {
        val body = json(get("api/voice/config"))
        val list = body.optJSONArray("voices") ?: JSONArray()
        val voices = (0 until list.length()).map { index ->
            val voice = list.getJSONObject(index)
            Voice(voice.getString("id"), voice.optString("name", voice.getString("id")))
        }
        return VoiceConfig(body.optBoolean("available", false), voices, body.optString("default_voice", ""))
    }

    suspend fun listConversations(): List<ConversationSummary> {
        val array = JSONArray(text(get("api/conversations")))
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            ConversationSummary(item.getString("id"), item.optString("title"), item.optBoolean("active"))
        }
    }

    /** Nowa rozmowa; bez tytułu serwer nada go z pierwszej wiadomości. */
    suspend fun createConversation(title: String? = null): String {
        val payload = JSONObject()
        if (title != null) payload.put("title", title)
        return json(post("api/conversations", payload)).getString("id")
    }

    /** Identyfikator trwającego zadania rozmowy albo `null`. */
    suspend fun activeRun(conversationId: String): String? =
        json(get("api/conversations/$conversationId")).optJSONObject("active_run")?.optString("id")

    /** Wysyła wiadomość; zwraca identyfikator zadania. Kod 409 – poprzednie zadanie jeszcze trwa. */
    suspend fun sendMessage(conversationId: String, text: String, voice: Boolean = false): String {
        val payload = JSONObject().put("text", text).put("voice", voice).put("file_ids", JSONArray())
        return json(post("api/conversations/$conversationId/messages", payload)).getString("run_id")
    }

    /** Stan zadania: `queued`, `running`, `done`, `failed`, `cancelled`. */
    suspend fun runStatus(runId: String): RunStatus {
        val body = json(get("api/runs/$runId"))
        return RunStatus(runId, body.optString("status"), body.optString("conversation_id"), body.optString("error"))
    }

    suspend fun cancelRun(runId: String) {
        text(post("api/runs/$runId/cancel", JSONObject()))
    }

    /** Rozpoznaje mowę z nagrania WAV. */
    suspend fun transcribe(wav: ByteArray, language: String = "pl"): String {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("audio", "wypowiedz.wav", wav.toRequestBody("audio/wav".toMediaType()))
            .addFormDataPart("language", language)
            .build()
        return json(request("api/voice/transcribe").post(body).build()).optString("text", "").trim()
    }

    /** Synteza mowy: MP3 (Google Cloud) albo WAV (głos lokalny). */
    suspend fun speak(text: String, voice: String, speed: Double = 1.0): SpeechAudio {
        val payload = JSONObject().put("text", text.take(MAX_SPEAK_CHARS)).put("voice", voice).put("speed", speed)
        return execute(post("api/voice/speak", payload)) { response ->
            val mime = response.header("Content-Type", "audio/mpeg")!!.substringBefore(';').trim()
            SpeechAudio(response.body!!.bytes(), mime)
        }
    }

    /**
     * Zdarzenia zadania (SSE) aż do zdarzenia końcowego. Po zerwaniu połączenia strumień jest
     * wznawiany od ostatniego zdarzenia (`after`), najwyżej [MAX_RECONNECTS] razy z rzędu.
     */
    fun runEvents(runId: String, after: Long = 0): Flow<RunEvent> =
        flow {
            var cursor = after
            var failures = 0
            while (currentCoroutineContext().isActive) {
                val url = base.newBuilder().addPathSegments("api/runs/$runId/events")
                    .addQueryParameter("after", cursor.toString()).build()
                val call = stream.newCall(authorized(Request.Builder().url(url)).header("Accept", "text/event-stream").build())
                val job = currentCoroutineContext()[kotlinx.coroutines.Job]
                val handle = job?.invokeOnCompletion { call.cancel() }
                var finished = false
                try {
                    call.execute().use { response ->
                        if (!response.isSuccessful) throw error(response)
                        val source = response.body!!.source()
                        val parser = SseParser()
                        while (true) {
                            val line = source.readUtf8Line() ?: break
                            val event = parser.feed(line) ?: continue
                            val id = event.id?.toLongOrNull() ?: cursor
                            cursor = maxOf(cursor, id)
                            failures = 0
                            val data = try {
                                JSONObject(event.data)
                            } catch (_: JSONException) {
                                JSONObject()
                            }
                            val runEvent = RunEvent(id, event.event, data)
                            emit(runEvent)
                            if (runEvent.final) {
                                finished = true
                                break
                            }
                        }
                    }
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: ApiException) {
                    throw failure
                } catch (failure: IOException) {
                    if (!currentCoroutineContext().isActive) return@flow
                    if (failures + 1 > MAX_RECONNECTS) throw failure
                } finally {
                    handle?.dispose()
                }
                if (finished) return@flow
                failures++
                if (failures > MAX_RECONNECTS) throw IOException("Utracono połączenie ze strumieniem zadania.")
                delay(RECONNECT_DELAY_MS)
            }
        }.flowOn(Dispatchers.IO)

    // --- pomocnicze ------------------------------------------------------------------------

    private fun request(path: String): Request.Builder =
        authorized(Request.Builder().url(base.newBuilder().addPathSegments(path).build()))

    private fun authorized(builder: Request.Builder): Request.Builder {
        val key = token() ?: throw ApiException(401, "Aplikacja nie jest połączona z Nexusem – zaloguj się w aplikacji.")
        return builder.header("Authorization", "Bearer $key").header("Accept", "application/json")
    }

    private fun get(path: String): Request = request(path).get().build()

    private fun post(path: String, payload: JSONObject): Request =
        request(path).post(payload.toString().toRequestBody(JSON)).build()

    private suspend fun json(request: Request): JSONObject = JSONObject(text(request))

    private suspend fun text(request: Request): String = execute(request) { it.body?.string().orEmpty() }

    private suspend fun <T> execute(request: Request, read: (Response) -> T): T {
        val call = http.newCall(request)
        val response = call.await()
        return response.use {
            if (!it.isSuccessful) throw error(it)
            read(it)
        }
    }

    companion object {
        const val MAX_SPEAK_CHARS = 1200
        private const val STREAM_READ_TIMEOUT_S = 60L
        private const val MAX_RECONNECTS = 5
        private const val RECONNECT_DELAY_MS = 2000L
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient =
            OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(90, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()

        /** Komunikat błędu z odpowiedzi FastAPI (`{"detail": "…"}` albo lista błędów walidacji). */
        fun error(response: Response): ApiException {
            val body = try {
                response.body?.string().orEmpty()
            } catch (_: IOException) {
                ""
            }
            return ApiException(response.code, detailMessage(body) ?: "Błąd serwera (${response.code}).")
        }

        fun detailMessage(body: String): String? {
            val detail = try {
                JSONObject(body).opt("detail")
            } catch (_: JSONException) {
                return null
            }
            return when (detail) {
                is String -> detail
                is JSONArray -> (0 until detail.length()).mapNotNull { detail.optJSONObject(it)?.optString("msg") }
                    .joinToString("; ").ifBlank { null }
                else -> null
            }
        }
    }
}

/** Wykonanie żądania OkHttp w korutynie z anulowaniem połączenia przy anulowaniu korutyny. */
suspend fun Call.await(): Response =
    suspendCancellableCoroutine { continuation ->
        enqueue(
            object : Callback {
                override fun onResponse(call: Call, response: Response) {
                    continuation.resume(response) { _, value, _ -> value.close() }
                }

                override fun onFailure(call: Call, e: IOException) {
                    if (!continuation.isCancelled) continuation.resumeWithException(e)
                }
            },
        )
        continuation.invokeOnCancellation { cancel() }
    }
