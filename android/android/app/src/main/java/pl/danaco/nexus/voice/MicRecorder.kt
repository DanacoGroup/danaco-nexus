package pl.danaco.nexus.voice

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.AutomaticGainControl
import android.media.audiofx.NoiseSuppressor
import android.media.audiofx.AudioEffect
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat

/**
 * Nagrywanie z mikrofonu z wykrywaniem mowy (wątek w tle, ramki 40 ms, 16 kHz mono).
 * Wypowiedź obejmuje ~600 ms dźwięku sprzed wykrycia mowy, żeby nie ucinać pierwszej sylaby.
 * Tryb [capture] ustawia właściciel: `OFF` (rozpoznawanie, myślenie, pauza), `LISTEN`, `SPEAK`
 * (odtwarzanie odpowiedzi – wykrywane jest tylko przerwanie głosem).
 */
class MicRecorder(private val context: Context, private val listener: Listener) {
    interface Listener {
        fun onLevel(rms: Double) {}

        fun onSpeechStarted() {}

        /** Pełna wypowiedź (PCM 16 kHz). Po niej nagrywanie przechodzi w tryb `OFF`. */
        fun onUtterance(pcm: ShortArray, forced: Boolean)

        /** Przerwanie odpowiedzi głosem; od tej chwili trwa wypowiedź (tryb `LISTEN`). */
        fun onBargeIn() {}

        fun onError(error: Exception)
    }

    enum class Capture { OFF, LISTEN, SPEAK }

    @Volatile
    var capture: Capture = Capture.OFF

    @Volatile
    private var running = false
    private var thread: Thread? = null
    private val effects = mutableListOf<AudioEffect>()

    val hasPermission: Boolean
        get() = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    /** Uruchamia mikrofon; `false`, gdy brak zgody lub mikrofon jest zajęty. */
    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (running) return true
        if (!hasPermission) return false
        val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuffer <= 0) return false
        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuffer, FRAME_SAMPLES * 2 * 8),
            )
        } catch (error: Exception) {
            Log.w(TAG, "Nie można otworzyć mikrofonu", error)
            return false
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            return false
        }
        attachEffects(record.audioSessionId)
        running = true
        thread = Thread({ loop(record) }, "nexus-mikrofon").apply { start() }
        return true
    }

    fun stop() {
        running = false
        thread?.join(500)
        thread = null
        effects.forEach { runCatching { it.release() } }
        effects.clear()
    }

    private fun attachEffects(session: Int) {
        // Usuwanie echa i szumu – żeby przerwanie głosem nie reagowało na własną odpowiedź.
        if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(session)?.let { it.enabled = true; effects += it }
        if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(session)?.let { it.enabled = true; effects += it }
        if (AutomaticGainControl.isAvailable()) AutomaticGainControl.create(session)?.let { it.enabled = true; effects += it }
    }

    private fun loop(record: AudioRecord) {
        val vad = Vad()
        val preRoll = ArrayDeque<ShortArray>()
        val utterance = ArrayList<ShortArray>()
        var lastCapture = Capture.OFF
        try {
            record.startRecording()
            while (running) {
                val frame = ShortArray(FRAME_SAMPLES)
                var read = 0
                while (read < FRAME_SAMPLES && running) {
                    val count = record.read(frame, read, FRAME_SAMPLES - read)
                    if (count < 0) throw IllegalStateException("Błąd odczytu mikrofonu ($count).")
                    read += count
                }
                if (!running) break
                val rms = Vad.rms(frame)
                listener.onLevel(rms)
                val mode = capture
                if (mode != lastCapture) {
                    if (mode == Capture.OFF || lastCapture == Capture.OFF) {
                        vad.reset()
                        utterance.clear()
                    }
                    lastCapture = mode
                }
                if (mode == Capture.OFF) {
                    remember(preRoll, frame)
                    continue
                }
                val wasHearing = vad.hearing
                val event = vad.process(rms, SystemClock.elapsedRealtime(), if (mode == Capture.SPEAK) Vad.Mode.SPEAKING else Vad.Mode.LISTENING)
                when (event) {
                    is Vad.Event.SpeechStarted -> {
                        utterance.clear()
                        utterance.addAll(preRoll)
                        utterance.add(frame)
                        preRoll.clear()
                        listener.onSpeechStarted()
                    }
                    is Vad.Event.BargeIn -> {
                        capture = Capture.LISTEN
                        lastCapture = Capture.LISTEN
                        utterance.clear()
                        utterance.addAll(preRoll)
                        utterance.add(frame)
                        preRoll.clear()
                        listener.onBargeIn()
                    }
                    is Vad.Event.UtteranceEnded -> {
                        utterance.add(frame)
                        val pcm = concat(utterance)
                        utterance.clear()
                        capture = Capture.OFF
                        lastCapture = Capture.OFF
                        vad.reset()
                        listener.onUtterance(pcm, event.forced)
                    }
                    null -> if (wasHearing) utterance.add(frame) else remember(preRoll, frame)
                }
            }
        } catch (error: Exception) {
            if (running) listener.onError(error)
        } finally {
            running = false
            runCatching { record.stop() }
            record.release()
        }
    }

    private fun remember(preRoll: ArrayDeque<ShortArray>, frame: ShortArray) {
        preRoll.addLast(frame)
        while (preRoll.size > PRE_ROLL_FRAMES) preRoll.removeFirst()
    }

    companion object {
        private const val TAG = "NexusMikrofon"
        const val SAMPLE_RATE = 16_000
        const val FRAME_SAMPLES = SAMPLE_RATE * 40 / 1000
        private const val PRE_ROLL_FRAMES = 15

        fun concat(frames: List<ShortArray>): ShortArray {
            val result = ShortArray(frames.sumOf { it.size })
            var offset = 0
            for (frame in frames) {
                frame.copyInto(result, offset)
                offset += frame.size
            }
            return result
        }
    }
}
