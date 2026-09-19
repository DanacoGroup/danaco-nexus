package pl.danaco.nexus.overlay

import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics

/**
 * Jednorazowy zrzut ekranu przez MediaProjection: pierwsza klatka po [delayMs], potem projekcja
 * jest natychmiast zatrzymywana (ikona nagrywania znika).
 */
class ScreenCapture(
    private val projection: MediaProjection,
    private val metrics: DisplayMetrics,
    private val delayMs: Long = 400,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var done = false

    fun capture(onResult: (Bitmap?) -> Unit) {
        projection.registerCallback(
            object : MediaProjection.Callback() {
                override fun onStop() {
                    finish(null, onResult)
                }
            },
            handler,
        )
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val images = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        reader = images
        val readyAt = SystemClock.elapsedRealtime() + delayMs
        images.setOnImageAvailableListener({ source ->
            val image = source.acquireLatestImage() ?: return@setOnImageAvailableListener
            image.use {
                if (done || SystemClock.elapsedRealtime() < readyAt) return@setOnImageAvailableListener
                val plane = it.planes[0]
                val rowPadding = plane.rowStride - plane.pixelStride * width
                val padded = Bitmap.createBitmap(width + rowPadding / plane.pixelStride, height, Bitmap.Config.ARGB_8888)
                padded.copyPixelsFromBuffer(plane.buffer)
                val bitmap = if (padded.width == width) padded else Bitmap.createBitmap(padded, 0, 0, width, height).also { padded.recycle() }
                finish(bitmap, onResult)
            }
        }, handler)
        display = projection.createVirtualDisplay(
            "nexus-zrzut",
            width,
            height,
            metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            images.surface,
            null,
            handler,
        )
        // Zabezpieczenie: brak klatki (np. ekran bez zmian) – po 3 s kończy bez obrazu.
        handler.postDelayed({ finish(null, onResult) }, delayMs + 3000)
    }

    private fun finish(bitmap: Bitmap?, onResult: (Bitmap?) -> Unit) {
        if (done) return
        done = true
        handler.removeCallbacksAndMessages(null)
        display?.release()
        reader?.close()
        runCatching { projection.stop() }
        onResult(bitmap)
    }
}
