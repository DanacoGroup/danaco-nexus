package pl.danaco.nexus.voice

import kotlin.math.max
import kotlin.math.sqrt

/**
 * Energetyczne wykrywanie mowy (VAD) – te same progi co `frontend/src/voice/VoiceMode.tsx`:
 * start mowy po 200 ms powyżej progu, koniec po 700 ms ciszy (min. 350 ms mowy), najwyżej 60 s,
 * przerwanie odpowiedzi głosem po 180 ms wyraźnie głośniejszego dźwięku niż echo.
 * Klasa jest czysta (bez API Androida) – wywoływana co ramkę z wartością RMS i czasem w ms.
 */
class Vad(private val params: Params = Params()) {
    data class Params(
        val speechStartMs: Long = 200,
        val speechEndSilenceMs: Long = 700,
        val minSpeechMs: Long = 350,
        val maxUtteranceMs: Long = 60_000,
        val bargeInMs: Long = 180,
        val minStartThreshold: Double = 0.018,
        val startFactor: Double = 3.0,
        val minBargeThreshold: Double = 0.05,
        val bargeFactor: Double = 6.0,
        val initialFloor: Double = 0.01,
    )

    /** Co robi rozmowa: słucha użytkownika albo czyta odpowiedź (wtedy wykrywane jest przerwanie). */
    enum class Mode { LISTENING, SPEAKING }

    sealed interface Event {
        /** Początek wypowiedzi (czas pierwszej ramki powyżej progu). */
        data class SpeechStarted(val startMs: Long) : Event

        /** Koniec wypowiedzi; [forced] – przekroczony limit długości. */
        data class UtteranceEnded(val startMs: Long, val endMs: Long, val forced: Boolean) : Event

        /** Użytkownik zaczął mówić w trakcie odpowiedzi – od tej chwili trwa wypowiedź. */
        data class BargeIn(val startMs: Long) : Event
    }

    /** Szacowany poziom tła (aktualizowany tylko w ciszy podczas słuchania). */
    var floor: Double = params.initialFloor
        private set

    /** Czy trwa wypowiedź użytkownika. */
    var hearing: Boolean = false
        private set

    private var aboveSince = 0L
    private var speechStart = 0L
    private var lastVoice = 0L

    val startThreshold: Double get() = max(params.minStartThreshold, floor * params.startFactor)
    val bargeThreshold: Double get() = max(params.minBargeThreshold, floor * params.bargeFactor)

    /** Zeruje stan wypowiedzi (poziom tła zostaje). */
    fun reset() {
        hearing = false
        aboveSince = 0
        speechStart = 0
        lastVoice = 0
    }

    /** Czas trwania bieżącej wypowiedzi w chwili [nowMs] (0, gdy nikt nie mówi). */
    fun speechLength(nowMs: Long): Long = if (hearing) nowMs - speechStart else 0

    /** Przetwarza jedną ramkę; zwraca zdarzenie albo `null`. */
    fun process(rms: Double, nowMs: Long, mode: Mode): Event? =
        when (mode) {
            Mode.LISTENING -> listen(rms, nowMs)
            Mode.SPEAKING -> speaking(rms, nowMs)
        }

    private fun listen(rms: Double, now: Long): Event? {
        val threshold = startThreshold
        if (!hearing && rms < threshold) floor = floor * 0.97 + rms * 0.03
        var event: Event? = null
        if (rms > threshold) {
            if (aboveSince == 0L) aboveSince = now
            lastVoice = now
            if (!hearing && now - aboveSince > params.speechStartMs) {
                hearing = true
                speechStart = aboveSince
                event = Event.SpeechStarted(speechStart)
            }
        } else {
            aboveSince = 0
        }
        if (hearing && event == null) {
            val silence = now - lastVoice
            val length = now - speechStart
            val forced = length > params.maxUtteranceMs
            if ((silence > params.speechEndSilenceMs && length > params.minSpeechMs) || forced) {
                hearing = false
                aboveSince = 0
                return Event.UtteranceEnded(speechStart, now, forced)
            }
        }
        return event
    }

    private fun speaking(rms: Double, now: Long): Event? {
        if (rms > bargeThreshold) {
            if (aboveSince == 0L) aboveSince = now
            if (now - aboveSince > params.bargeInMs) {
                hearing = true
                speechStart = aboveSince
                lastVoice = now
                return Event.BargeIn(speechStart)
            }
        } else {
            aboveSince = 0
        }
        return null
    }

    companion object {
        /** RMS ramki 16-bitowego PCM w skali 0..1 (jak getFloatTimeDomainData w przeglądarce). */
        fun rms(samples: ShortArray, count: Int = samples.size): Double {
            if (count <= 0) return 0.0
            var sum = 0.0
            for (index in 0 until count) {
                val value = samples[index] / 32768.0
                sum += value * value
            }
            return sqrt(sum / count)
        }
    }
}
