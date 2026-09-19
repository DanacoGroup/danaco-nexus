package pl.danaco.nexus.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VadTest {
    private val frame = 40L

    /** Podaje ramki o stałym poziomie od chwili [start]; zwraca zdarzenia i czas końca. */
    private fun Vad.feed(level: Double, durationMs: Long, start: Long, mode: Vad.Mode = Vad.Mode.LISTENING): Pair<List<Vad.Event>, Long> {
        val events = mutableListOf<Vad.Event>()
        var now = start
        while (now < start + durationMs) {
            process(level, now, mode)?.let { events += it }
            now += frame
        }
        return events to now
    }

    @Test
    fun `cisza nie uruchamia wypowiedzi i obniza poziom tla`() {
        val vad = Vad()
        val (events, _) = vad.feed(0.002, 3000, 0)
        assertTrue(events.isEmpty())
        assertTrue(vad.floor < 0.01)
        assertEquals(0.018, vad.startThreshold, 1e-9)
    }

    @Test
    fun `mowa po 200 ms rozpoczyna wypowiedz a 700 ms ciszy ja konczy`() {
        val vad = Vad()
        val (silence, t1) = vad.feed(0.003, 1000, 0)
        assertTrue(silence.isEmpty())
        val (speech, t2) = vad.feed(0.2, 1200, t1)
        val started = speech.single() as Vad.Event.SpeechStarted
        assertEquals(t1, started.startMs)
        assertTrue(vad.hearing)
        val (end, _) = vad.feed(0.003, 1000, t2)
        val ended = end.single() as Vad.Event.UtteranceEnded
        assertEquals(t1, ended.startMs)
        assertFalse(ended.forced)
        // Ostatnia głośna ramka to t2 − 40 ms; koniec, gdy cisza przekroczy 700 ms od niej.
        assertEquals(t2 + 680, ended.endMs)
        assertFalse(vad.hearing)
    }

    @Test
    fun `krotki trzask nie jest mowa`() {
        val vad = Vad()
        val (_, t1) = vad.feed(0.003, 500, 0)
        val (click, t2) = vad.feed(0.3, 120, t1)
        val (after, _) = vad.feed(0.003, 1500, t2)
        assertTrue(click.isEmpty())
        assertTrue(after.isEmpty())
    }

    @Test
    fun `zbyt dluga wypowiedz jest konczona po 60 s`() {
        val vad = Vad()
        val (events, _) = vad.feed(0.2, 61_000, 0)
        assertTrue(events.first() is Vad.Event.SpeechStarted)
        val forced = events.filterIsInstance<Vad.Event.UtteranceEnded>().single()
        assertTrue(forced.forced)
        assertEquals(0L, forced.startMs)
        assertTrue(forced.endMs in 60_000..60_100)
    }

    @Test
    fun `przerwanie wymaga glosniejszego dzwieku niz echo`() {
        val vad = Vad()
        val (echo, t1) = vad.feed(0.04, 1000, 0, Vad.Mode.SPEAKING)
        assertTrue(echo.isEmpty())
        val (barge, _) = vad.feed(0.2, 400, t1, Vad.Mode.SPEAKING)
        val event = barge.first() as Vad.Event.BargeIn
        assertEquals(t1, event.startMs)
        assertTrue(vad.hearing)
    }

    @Test
    fun `reset konczy wypowiedz bez zmiany poziomu tla`() {
        val vad = Vad()
        vad.feed(0.004, 2000, 0)
        val floor = vad.floor
        vad.feed(0.2, 500, 2000)
        vad.reset()
        assertFalse(vad.hearing)
        assertEquals(floor, vad.floor, 1e-12)
        assertNull(vad.process(0.004, 3000, Vad.Mode.LISTENING))
    }

    @Test
    fun `rms ramki pcm`() {
        assertEquals(0.0, Vad.rms(ShortArray(640)), 1e-12)
        val full = ShortArray(640) { if (it % 2 == 0) Short.MAX_VALUE else Short.MIN_VALUE }
        assertEquals(1.0, Vad.rms(full), 0.001)
        assertEquals(0.0, Vad.rms(ShortArray(0)), 1e-12)
    }
}
