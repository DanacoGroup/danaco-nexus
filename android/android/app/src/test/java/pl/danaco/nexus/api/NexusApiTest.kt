package pl.danaco.nexus.api

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class NexusApiTest {
    private lateinit var server: MockWebServer
    private var token: String? = "nxd_testowyKluczUrzadzenia123456"
    private lateinit var api: NexusApi

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        api = NexusApi(server.url("/").toString(), { token })
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    @Test
    fun `klucz urzadzenia w naglowku bez csrf i ciasteczek`() = runBlocking {
        server.enqueue(json("""{"username": "admin", "cloud_url": ""}"""))
        assertEquals("admin", api.me())
        val request = server.takeRequest()
        assertEquals("/api/auth/me", request.path)
        assertEquals("Bearer nxd_testowyKluczUrzadzenia123456", request.getHeader("Authorization"))
        assertNull(request.getHeader("X-Nexus-Request"))
        assertNull(request.getHeader("Cookie"))
    }

    @Test
    fun `bez klucza zadanie nie jest wysylane`() = runBlocking {
        token = null
        try {
            api.me()
            fail("oczekiwano błędu")
        } catch (error: ApiException) {
            assertTrue(error.unauthorized)
        }
        assertEquals(0, server.requestCount)
    }

    @Test
    fun `wiadomosc glosowa i identyfikator zadania`() = runBlocking {
        server.enqueue(json("""{"id": "c1", "title": "Nowa rozmowa", "updated_at": "x", "active": false}""", 201))
        server.enqueue(json("""{"run_id": "r1"}""", 202))
        val conversation = api.createConversation()
        assertEquals("r1", api.sendMessage(conversation, "Jaka jest pogoda?", voice = true))
        val create = server.takeRequest()
        assertEquals("{}", create.body.readUtf8())
        val send = server.takeRequest()
        assertEquals("/api/conversations/c1/messages", send.path)
        val body = JSONObject(send.body.readUtf8())
        assertEquals("Jaka jest pogoda?", body.getString("text"))
        assertTrue(body.getBoolean("voice"))
        assertEquals(0, body.getJSONArray("file_ids").length())
    }

    @Test
    fun `blad 409 z komunikatem serwera`() = runBlocking {
        server.enqueue(json("""{"detail": "Poprzednie zadanie jeszcze trwa."}""", 409))
        try {
            api.sendMessage("c1", "tekst")
            fail("oczekiwano błędu")
        } catch (error: ApiException) {
            assertEquals(409, error.status)
            assertEquals("Poprzednie zadanie jeszcze trwa.", error.message)
            assertFalse(error.unauthorized)
        }
    }

    @Test
    fun `komunikat bledu walidacji fastapi`() {
        assertEquals("pole wymagane", NexusApi.detailMessage("""{"detail": [{"msg": "pole wymagane"}]}"""))
        assertNull(NexusApi.detailMessage("<html>"))
    }

    @Test
    fun `rozpoznawanie mowy wysyla wav jako multipart`() = runBlocking {
        server.enqueue(json("""{"text": "  dzień dobry ", "language": "pl", "duration": 1.2}"""))
        val text = api.transcribe(byteArrayOf(1, 2, 3))
        assertEquals("dzień dobry", text)
        val request = server.takeRequest()
        assertEquals("/api/voice/transcribe", request.path)
        assertTrue(request.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val body = request.body.readUtf8()
        assertTrue(body.contains("name=\"audio\"; filename=\"wypowiedz.wav\""))
        assertTrue(body.contains("name=\"language\""))
    }

    @Test
    fun `synteza zwraca dzwiek i typ`() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "audio/mpeg").setBody("ID3abc"))
        val audio = api.speak("Dzień dobry.", "pl-PL-Chirp3-HD-Aoede")
        assertEquals("audio/mpeg", audio.mime)
        assertEquals("ID3abc", String(audio.bytes))
        val body = JSONObject(server.takeRequest().body.readUtf8())
        assertEquals("pl-PL-Chirp3-HD-Aoede", body.getString("voice"))
    }

    @Test
    fun `konfiguracja glosu`() = runBlocking {
        server.enqueue(json("""{"available": true, "voices": [{"id": "gosia", "name": "Gosia"}], "default_voice": "gosia"}"""))
        val config = api.voiceConfig()
        assertTrue(config.available)
        assertEquals(listOf(Voice("gosia", "Gosia")), config.voices)
        assertEquals("gosia", config.defaultVoice)
    }

    @Test
    fun `strumien zdarzen do zdarzenia koncowego`() = runBlocking {
        server.enqueue(
            MockResponse().setHeader("Content-Type", "text/event-stream").setBody(
                "retry: 2000\n\n" +
                    "id: 1\nevent: run.started\ndata: {}\n\n" +
                    "id: 2\nevent: text.delta\ndata: {\"text\": \"Dzień \"}\n\n" +
                    "id: 3\nevent: text.delta\ndata: {\"text\": \"dobry.\"}\n\n" +
                    "id: 4\nevent: run.completed\ndata: {\"error\": \"\"}\n\n" +
                    "id: 5\nevent: text.delta\ndata: {\"text\": \"nie powinno\"}\n\n",
            ),
        )
        val events = api.runEvents("r1").toList()
        assertEquals(listOf("run.started", "text.delta", "text.delta", "run.completed"), events.map { it.type })
        assertEquals("Dzień dobry.", events.filter { it.type == "text.delta" }.joinToString("") { it.text })
        assertTrue(events.last().final)
        assertEquals("/api/runs/r1/events?after=0", server.takeRequest().path)
    }

    @Test
    fun `wznowienie strumienia od ostatniego zdarzenia`() = runBlocking {
        server.enqueue(
            MockResponse().setHeader("Content-Type", "text/event-stream")
                .setBody("id: 7\nevent: text.delta\ndata: {\"text\": \"A\"}\n\n")
                .setSocketPolicy(SocketPolicy.DISCONNECT_AT_END),
        )
        server.enqueue(
            MockResponse().setHeader("Content-Type", "text/event-stream")
                .setBody("id: 8\nevent: run.failed\ndata: {\"error\": \"Błąd\"}\n\n"),
        )
        val events = api.runEvents("r2").toList()
        assertEquals(listOf(7L, 8L), events.map { it.id })
        assertEquals("/api/runs/r2/events?after=0", server.takeRequest(5, TimeUnit.SECONDS)!!.path)
        assertEquals("/api/runs/r2/events?after=7", server.takeRequest(5, TimeUnit.SECONDS)!!.path)
    }

    @Test
    fun `stan zadania`() = runBlocking {
        server.enqueue(json("""{"id": "r1", "status": "running", "error": "", "usage": {}, "conversation_id": "c1"}"""))
        val status = api.runStatus("r1")
        assertTrue(status.active)
        assertEquals("c1", status.conversationId)
    }
}
