package pl.danaco.nexus.assist

import android.content.Intent
import android.os.Bundle
import android.os.RemoteException
import android.speech.RecognitionService
import android.speech.SpeechRecognizer
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.launch
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.api.ApiException
import pl.danaco.nexus.voice.MicRecorder
import pl.danaco.nexus.voice.Wav

/**
 * Rozpoznawanie mowy Nexusa (wymagane przez system dla asystenta cyfrowego): jedna wypowiedź
 * z wykrywaniem końca mowy, rozpoznana na serwerze (`/api/voice/transcribe`).
 */
class NexusRecognitionService : RecognitionService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var recorder: MicRecorder? = null

    override fun onStartListening(intent: Intent?, listener: Callback) {
        stopRecorder()
        val language = intent?.getStringExtra("android.speech.extra.LANGUAGE")?.substringBefore('-')?.lowercase()
            ?.takeIf { it.length in 2..3 && it.all(Char::isLetter) } ?: "pl"
        val mic = MicRecorder(
            this,
            object : MicRecorder.Listener {
                override fun onLevel(rms: Double) {
                    val db = (rms * 100).toFloat().coerceIn(0f, 10f)
                    scope.launch { safe { listener.rmsChanged(db) } }
                }

                override fun onSpeechStarted() {
                    scope.launch { safe { listener.beginningOfSpeech() } }
                }

                override fun onUtterance(pcm: ShortArray, forced: Boolean) {
                    scope.launch { finish(pcm, language, listener) }
                }

                override fun onError(error: Exception) {
                    scope.launch { safe { listener.error(SpeechRecognizer.ERROR_AUDIO) } }
                }
            },
        )
        if (!mic.hasPermission) {
            safe { listener.error(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) }
            return
        }
        if (!mic.start()) {
            safe { listener.error(SpeechRecognizer.ERROR_AUDIO) }
            return
        }
        recorder = mic
        mic.capture = MicRecorder.Capture.LISTEN
        safe { listener.readyForSpeech(Bundle()) }
    }

    private suspend fun finish(pcm: ShortArray, language: String, listener: Callback) {
        stopRecorder()
        safe { listener.endOfSpeech() }
        try {
            val text = Nexus.api(this).transcribe(Wav.encode(pcm, sampleRate = MicRecorder.SAMPLE_RATE), language)
            if (text.isBlank()) {
                safe { listener.error(SpeechRecognizer.ERROR_NO_MATCH) }
                return
            }
            val results = Bundle().apply {
                putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION, arrayListOf(text))
                putFloatArray(SpeechRecognizer.CONFIDENCE_SCORES, floatArrayOf(1f))
            }
            safe { listener.results(results) }
        } catch (error: ApiException) {
            Nexus.handleFailure(this, error)
            safe { listener.error(if (error.status == 503) SpeechRecognizer.ERROR_SERVER else SpeechRecognizer.ERROR_CLIENT) }
        } catch (error: Exception) {
            Log.w(TAG, "Rozpoznawanie nie powiodło się", error)
            safe { listener.error(SpeechRecognizer.ERROR_NETWORK) }
        }
    }

    override fun onStopListening(listener: Callback) {
        recorder?.capture = MicRecorder.Capture.OFF
        stopRecorder()
        safe { listener.error(SpeechRecognizer.ERROR_SPEECH_TIMEOUT) }
    }

    override fun onCancel(listener: Callback) {
        scope.coroutineContext.cancelChildren()
        stopRecorder()
    }

    private fun stopRecorder() {
        recorder?.stop()
        recorder = null
    }

    override fun onDestroy() {
        stopRecorder()
        scope.cancel()
        super.onDestroy()
    }

    private inline fun safe(block: () -> Unit) {
        try {
            block()
        } catch (_: RemoteException) {
            // Klient rozpoznawania już się rozłączył.
        }
    }

    private companion object {
        const val TAG = "NexusRozpoznawanie"
    }
}
