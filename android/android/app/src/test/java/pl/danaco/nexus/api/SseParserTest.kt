package pl.danaco.nexus.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SseParserTest {
    private fun parse(stream: String): Pair<List<SseEvent>, SseParser> {
        val parser = SseParser()
        return stream.split("\n").mapNotNull { parser.feed(it) } to parser
    }

    @Test
    fun `zdarzenia jak z api runs events`() {
        val (events, parser) = parse(
            "retry: 2000\n\n" +
                "id: 5\nevent: text.delta\ndata: {\"text\": \"Dzień\"}\n\n" +
                ": keepalive\n\n" +
                "id: 6\nevent: run.completed\ndata: {\"error\": \"\", \"usage\": {}}\n\n",
        )
        assertEquals(2, events.size)
        assertEquals(SseEvent("5", "text.delta", "{\"text\": \"Dzień\"}"), events[0])
        assertEquals("run.completed", events[1].event)
        assertEquals("6", parser.lastEventId)
    }

    @Test
    fun `wiele linii danych i brak nazwy zdarzenia`() {
        val (events, _) = parse("data: a\ndata:b\n\n")
        assertEquals(listOf(SseEvent(null, "message", "a\nb")), events)
    }

    @Test
    fun `pusta linia bez danych nie tworzy zdarzenia`() {
        val parser = SseParser()
        assertNull(parser.feed("event: nic"))
        assertNull(parser.feed(""))
    }
}
