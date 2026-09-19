package pl.danaco.nexus.voice

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import java.io.IOException
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.R
import pl.danaco.nexus.api.ApiException
import pl.danaco.nexus.api.NexusApi
import pl.danaco.nexus.api.SpeechAudio
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.notify.Notifications

/**
 * Rozmowa głosowa w tle (usługa pierwszoplanowa `microphone|mediaPlayback`): działa przy wygaszonym
 * ekranie i po przełączeniu aplikacji. Pętla jak w przeglądarce: słuchanie z wykrywaniem mowy →
 * `/api/voice/transcribe` → wiadomość `voice=true` → zdarzenia zadania → `/api/voice/speak` zdanie po zdaniu.
 */
class VoiceService : Service() {
    enum class Phase(val label: String) {
        STARTING("Przygotowuję mikrofon…"),
        LISTENING("Słucham…"),
        HEARING("Słucham…"),
        TRANSCRIBING("Rozpoznaję…"),
        THINKING("Myślę…"),
        SPEAKING("Mówię – możesz przerwać"),
        PAUSED("Wstrzymano"),
        ERROR("Błąd"),
        STOPPED("Zakończono"),
    }

    data class State(
        val phase: Phase = Phase.STOPPED,
        val heard: String = "",
        val error: String = "",
        val conversationId: String? = null,
    ) {
        val running: Boolean get() = phase != Phase.STOPPED
    }

    private sealed interface MicEvent {
        data class Utterance(val pcm: ShortArray) : MicEvent

        data object BargeIn : MicEvent

        data object SpeechStarted : MicEvent

        data class Failure(val error: Exception) : MicEvent
    }

    private val scope = CoroutineScope(
        SupervisorJob() + Dispatchers.Main.immediate + CoroutineExceptionHandler { _, error ->
            Log.e(TAG, "Nieoczekiwany błąd rozmowy głosowej", error)
            fail("Nieoczekiwany błąd rozmowy głosowej.")
        },
    )
    private val micEvents = Channel<MicEvent>(Channel.UNLIMITED)
    private lateinit var api: NexusApi
    private lateinit var recorder: MicRecorder
    private lateinit var player: SpeechPlayer
    private lateinit var audio: AudioManager
    private var focus: AudioFocusRequest? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var replyJob: Job? = null
    private var voice = ""
    private var conversationId: String? = null
    private var lastActivity = 0L
    private var started = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        api = Nexus.api(this)
        player = SpeechPlayer(this)
        audio = getSystemService(AudioManager::class.java)
        recorder = MicRecorder(
            this,
            object : MicRecorder.Listener {
                override fun onSpeechStarted() {
                    micEvents.trySend(MicEvent.SpeechStarted)
                }

                override fun onUtterance(pcm: ShortArray, forced: Boolean) {
                    micEvents.trySend(MicEvent.Utterance(pcm))
                }

                override fun onBargeIn() {
                    micEvents.trySend(MicEvent.BargeIn)
                }

                override fun onError(error: Exception) {
                    micEvents.trySend(MicEvent.Failure(error))
                }
            },
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PAUSE -> togglePause()
            ACTION_STOP -> stopSelf()
            else -> start(intent?.getStringExtra(EXTRA_CONVERSATION))
        }
        return START_NOT_STICKY
    }

    private fun start(conversation: String?) {
        if (!started) {
            started = true
            conversationId = conversation
            update(Phase.STARTING)
            try {
                ServiceCompat.startForeground(
                    this,
                    Notifications.ID_VOICE,
                    notification(),
                    foregroundType(),
                )
            } catch (error: Exception) {
                // Android nie pozwala uruchomić mikrofonu w tle bez widocznego okna aplikacji.
                Log.w(TAG, "Nie można uruchomić usługi pierwszoplanowej", error)
                stopSelf()
                return
            }
            acquireWakeLock()
            scope.launch { run() }
        } else if (conversation != null && conversation != conversationId) {
            conversationId = conversation
            update(state.value.phase)
        }
    }

    /** Mikrofon jako typ usługi istnieje od Androida 11; na Androidzie 10 wystarcza odtwarzanie. */
    private fun foregroundType(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE or ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        } else {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        }

    private suspend fun run() {
        if (!recorder.start()) {
            fail("Brak dostępu do mikrofonu. Zezwól Nexusowi na mikrofon w ustawieniach.")
            return
        }
        try {
            val config = api.voiceConfig()
            if (!config.available) {
                fail("Rozmowa głosowa jest niedostępna na serwerze.")
                return
            }
            val preferred = AppSettings(this).voice
            voice = config.voices.firstOrNull { it.id == preferred }?.id ?: config.defaultVoice
        } catch (error: Exception) {
            Nexus.handleFailure(this, error)
            fail(Nexus.describe(error))
            return
        }
        requestFocus()
        listen()
        scope.launch { idleWatch() }
        for (event in micEvents) {
            when (event) {
                MicEvent.SpeechStarted -> if (state.value.phase == Phase.LISTENING) update(Phase.HEARING)
                MicEvent.BargeIn -> {
                    replyJob?.cancel()
                    replyJob = null
                    update(Phase.HEARING)
                }
                is MicEvent.Utterance -> handleUtterance(event.pcm)
                is MicEvent.Failure -> {
                    fail("Mikrofon przestał działać: ${event.error.message ?: "błąd"}")
                    return
                }
            }
        }
    }

    private fun listen(error: String = "") {
        lastActivity = SystemClock.elapsedRealtime()
        recorder.capture = MicRecorder.Capture.LISTEN
        update(Phase.LISTENING, error = error)
    }

    private suspend fun handleUtterance(pcm: ShortArray) {
        if (state.value.phase == Phase.PAUSED) return
        lastActivity = SystemClock.elapsedRealtime()
        update(Phase.TRANSCRIBING)
        val text = try {
            api.transcribe(Wav.encode(pcm, sampleRate = MicRecorder.SAMPLE_RATE))
        } catch (error: Exception) {
            recoverable(error)
            return
        }
        if (state.value.phase != Phase.TRANSCRIBING) return
        if (text.length < 2) {
            listen()
            return
        }
        update(Phase.THINKING, heard = text)
        val runId = try {
            send(text)
        } catch (error: Exception) {
            recoverable(error)
            return
        }
        replyJob = scope.launch {
            try {
                speakReply(runId)
            } catch (error: IOException) {
                recoverable(error)
                return@launch
            }
            if (state.value.phase == Phase.THINKING || state.value.phase == Phase.SPEAKING) listen()
        }
    }

    /** Wysyła wypowiedź; gdy poprzednie zadanie jeszcze trwa – czeka na jego koniec (jak przeglądarka). */
    private suspend fun send(text: String): String {
        val conversation = conversationId ?: api.createConversation().also {
            conversationId = it
            update(state.value.phase)
        }
        repeat(3) {
            try {
                return api.sendMessage(conversation, text, voice = true)
            } catch (error: ApiException) {
                if (error.status != 409) throw error
                val active = api.activeRun(conversation) ?: return@repeat
                api.runEvents(active).collect { }
            }
        }
        return api.sendMessage(conversation, text, voice = true)
    }

    /** Czyta odpowiedź zdanie po zdaniu: synteza najwyżej dwóch fragmentów naprzód. */
    private suspend fun speakReply(runId: String) = coroutineScope {
        val sentences = Channel<String>(Channel.UNLIMITED)
        val reply = ReplySpeech()
        val sentAt = SystemClock.elapsedRealtime()
        val reader = launch {
            try {
                api.runEvents(runId).collect { event ->
                    when (event.type) {
                        "text.delta" -> reply.onDelta(event.text).forEach { sentences.send(it) }
                        "text.block" -> reply.onBlock()
                        "run.failed" -> sentences.send("Niestety, nie udało się dokończyć zadania.")
                    }
                }
                reply.finish().forEach { sentences.send(it) }
            } finally {
                sentences.close()
            }
        }
        val filler = launch {
            delay(FILLER_AFTER_MS)
            if (!reply.received && SystemClock.elapsedRealtime() - sentAt >= FILLER_AFTER_MS) sentences.send(FILLER)
        }
        val pending = ArrayDeque<Deferred<SpeechAudio>>()
        fun fill() {
            while (pending.size < 2) {
                val next = sentences.tryReceive().getOrNull() ?: break
                pending.addLast(async { api.speak(next, voice) })
            }
        }
        while (true) {
            fill()
            if (pending.isEmpty()) {
                if (state.value.phase == Phase.SPEAKING) {
                    recorder.capture = MicRecorder.Capture.OFF
                    update(Phase.THINKING)
                }
                val next = sentences.receiveCatching().getOrNull() ?: break
                pending.addLast(async { api.speak(next, voice) })
                continue
            }
            val speech = pending.removeFirst().await()
            fill()
            if (state.value.phase != Phase.THINKING && state.value.phase != Phase.SPEAKING) break
            filler.cancel()
            recorder.capture = MicRecorder.Capture.SPEAK
            update(Phase.SPEAKING)
            player.play(speech)
            lastActivity = SystemClock.elapsedRealtime()
        }
        filler.cancel()
        reader.join()
    }

    private fun recoverable(error: Exception) {
        Log.w(TAG, "Błąd rozmowy głosowej", error)
        Nexus.handleFailure(this, error)
        if (error is ApiException && error.unauthorized) {
            fail(Nexus.describe(error))
            return
        }
        if (state.value.phase == Phase.PAUSED || state.value.phase == Phase.ERROR) return
        listen(error = Nexus.describe(error))
    }

    private fun togglePause() {
        if (state.value.phase == Phase.PAUSED) {
            requestFocus()
            update(Phase.LISTENING, error = "")
            listen()
            return
        }
        replyJob?.cancel()
        replyJob = null
        recorder.capture = MicRecorder.Capture.OFF
        abandonFocus()
        update(Phase.PAUSED)
    }

    /** Po 10 minutach bez rozmowy usługa kończy się sama (oszczędzanie baterii). */
    private suspend fun idleWatch() {
        while (true) {
            delay(30_000)
            val phase = state.value.phase
            val idle = SystemClock.elapsedRealtime() - lastActivity
            if ((phase == Phase.LISTENING || phase == Phase.PAUSED) && idle > IDLE_STOP_MS) {
                stopSelf()
                return
            }
        }
    }

    private fun fail(message: String) {
        update(Phase.ERROR, error = message)
        recorder.capture = MicRecorder.Capture.OFF
        scope.launch {
            delay(4000)
            stopSelf()
        }
    }

    private fun requestFocus() {
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(SpeechPlayer.ATTRIBUTES)
            .setOnAudioFocusChangeListener { change ->
                // Rozmowa telefoniczna lub inna aplikacja przejmuje dźwięk – wstrzymanie.
                if (change == AudioManager.AUDIOFOCUS_LOSS || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
                    scope.launch { if (state.value.phase != Phase.PAUSED) togglePause() }
                }
            }
            .build()
        focus = request
        audio.requestAudioFocus(request)
    }

    private fun abandonFocus() {
        focus?.let { audio.abandonAudioFocusRequest(it) }
        focus = null
    }

    private fun acquireWakeLock() {
        val power = getSystemService(PowerManager::class.java)
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "nexus:rozmowa").apply {
            setReferenceCounted(false)
            acquire(MAX_SESSION_MS)
        }
    }

    private fun update(phase: Phase, heard: String? = null, error: String? = null) {
        val current = state.value
        mutableState.value = current.copy(
            phase = phase,
            heard = heard ?: current.heard,
            error = error ?: if (phase == Phase.ERROR) current.error else "",
            conversationId = conversationId,
        )
        if (started && phase != Phase.STOPPED) {
            getSystemService(android.app.NotificationManager::class.java).notify(Notifications.ID_VOICE, notification())
        }
    }

    private fun notification(): Notification {
        val current = state.value
        val paused = current.phase == Phase.PAUSED
        val text = when {
            current.error.isNotBlank() -> current.error
            current.heard.isNotBlank() && current.phase != Phase.LISTENING -> "${current.phase.label} „${current.heard.take(80)}”"
            else -> current.phase.label
        }
        return NotificationCompat.Builder(this, Notifications.CHANNEL_VOICE)
            .setSmallIcon(R.drawable.ic_stat_nexus)
            .setContentTitle(if (paused) "Nexus – rozmowa wstrzymana" else "Nexus słucha")
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setContentIntent(Notifications.openAppIntent(this, conversationId))
            .addAction(
                if (paused) R.drawable.ic_mic else R.drawable.ic_pause,
                if (paused) "Wznów" else "Wstrzymaj",
                action(ACTION_PAUSE, 1),
            )
            .addAction(R.drawable.ic_close, "Zakończ", action(ACTION_STOP, 2))
            .build()
    }

    private fun action(name: String, code: Int): PendingIntent =
        PendingIntent.getService(
            this,
            code,
            Intent(this, VoiceService::class.java).setAction(name),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

    override fun onDestroy() {
        replyJob?.cancel()
        scope.cancel()
        recorder.stop()
        abandonFocus()
        wakeLock?.let { if (it.isHeld) it.release() }
        mutableState.value = State()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "NexusGlos"
        const val ACTION_START = "pl.danaco.nexus.glos.START"
        const val ACTION_PAUSE = "pl.danaco.nexus.glos.PAUZA"
        const val ACTION_STOP = "pl.danaco.nexus.glos.STOP"
        const val EXTRA_CONVERSATION = "rozmowa"
        private const val FILLER_AFTER_MS = 4500L
        private const val FILLER = "Chwileczkę, już nad tym pracuję."
        private const val IDLE_STOP_MS = 10 * 60 * 1000L
        private const val MAX_SESSION_MS = 3 * 60 * 60 * 1000L

        private val mutableState = MutableStateFlow(State())

        /** Stan rozmowy dla paneli (asystent, języczek, ustawienia). */
        val state: StateFlow<State> = mutableState

        /** Uruchomienie z widocznego okna (wymóg Androida dla mikrofonu w tle). */
        fun start(context: Context, conversationId: String? = null) {
            val intent = Intent(context, VoiceService::class.java).setAction(ACTION_START)
            if (conversationId != null) intent.putExtra(EXTRA_CONVERSATION, conversationId)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.startService(Intent(context, VoiceService::class.java).setAction(ACTION_STOP))
        }
    }
}
