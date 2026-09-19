package pl.danaco.nexus.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import java.io.File
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import pl.danaco.nexus.api.SpeechAudio

/** Odtwarzanie odpowiedzi (MP3 z Google Cloud albo WAV z głosu lokalnego) jako mowy asystenta. */
class SpeechPlayer(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())

    /** Odtwarza nagranie do końca; anulowanie korutyny natychmiast przerywa odtwarzanie. */
    suspend fun play(audio: SpeechAudio) {
        val extension = if (audio.mime.contains("wav")) ".wav" else ".mp3"
        val file = withContext(Dispatchers.IO) {
            File.createTempFile("mowa", extension, context.cacheDir).apply { writeBytes(audio.bytes) }
        }
        try {
            withContext(Dispatchers.Main) { playFile(file) }
        } finally {
            file.delete()
        }
    }

    private suspend fun playFile(file: File) =
        suspendCancellableCoroutine { continuation ->
            val player = MediaPlayer()
            var released = false
            fun release() {
                if (released) return
                released = true
                runCatching { player.stop() }
                player.release()
            }
            player.setAudioAttributes(ATTRIBUTES)
            player.setOnCompletionListener {
                release()
                if (continuation.isActive) continuation.resume(Unit)
            }
            player.setOnErrorListener { _, what, extra ->
                release()
                if (continuation.isActive) continuation.resumeWithException(IOException("Błąd odtwarzania ($what/$extra)."))
                true
            }
            player.setOnPreparedListener { it.start() }
            try {
                player.setDataSource(file.path)
                player.prepareAsync()
            } catch (error: Exception) {
                release()
                continuation.resumeWithException(error)
                return@suspendCancellableCoroutine
            }
            continuation.invokeOnCancellation { main.post { release() } }
        }

    companion object {
        val ATTRIBUTES: AudioAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ASSISTANT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()
    }
}
