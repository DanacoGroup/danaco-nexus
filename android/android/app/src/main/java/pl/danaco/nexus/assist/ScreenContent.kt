package pl.danaco.nexus.assist

import android.app.assist.AssistStructure
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.text.InputType
import android.util.Base64
import android.view.View
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.roundToInt

/** Zamiana danych ekranu (struktura widoków, zrzut) na kontekst dla panelu Nexusa. */
object ScreenContent {
    private const val MAX_IMAGE_SIDE = 1280
    private const val JPEG_QUALITY = 75

    /** Tekst z drzewa widoków; pola haseł są pomijane. */
    fun text(structure: AssistStructure, limit: Int = 12_000): String {
        val collector = TextCollector(limit)
        for (index in 0 until structure.windowNodeCount) {
            val window = structure.getWindowNodeAt(index)
            walk(window.rootViewNode, collector)
            if (collector.full) break
        }
        return collector.text()
    }

    private fun walk(node: AssistStructure.ViewNode?, collector: TextCollector) {
        if (node == null || collector.full || node.visibility != View.VISIBLE) return
        if (!isPassword(node.inputType)) {
            collector.add(node.text)
            if (node.text.isNullOrBlank()) collector.add(node.contentDescription)
        }
        for (child in 0 until node.childCount) walk(node.getChildAt(child), collector)
    }

    fun isPassword(inputType: Int): Boolean {
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        val kind = inputType and InputType.TYPE_MASK_CLASS
        return (kind == InputType.TYPE_CLASS_TEXT &&
            (variation == InputType.TYPE_TEXT_VARIATION_PASSWORD ||
                variation == InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD ||
                variation == InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD)) ||
            (kind == InputType.TYPE_CLASS_NUMBER && variation == InputType.TYPE_NUMBER_VARIATION_PASSWORD)
    }

    /** Nazwa aplikacji na ekranie (albo nazwa pakietu, gdy etykieta jest niedostępna). */
    fun appLabel(context: Context, packageName: String?): String {
        if (packageName.isNullOrBlank()) return "Ekran"
        return try {
            val info = context.packageManager.getApplicationInfo(packageName, 0)
            context.packageManager.getApplicationLabel(info).toString()
        } catch (_: PackageManager.NameNotFoundException) {
            packageName
        }
    }

    /** Zrzut jako `data:image/jpeg;base64,…` (dłuższy bok najwyżej 1280 px). */
    fun dataUrl(bitmap: Bitmap): String {
        val scale = MAX_IMAGE_SIDE.toFloat() / max(bitmap.width, bitmap.height)
        val scaled = if (scale < 1f) {
            Bitmap.createScaledBitmap(bitmap, (bitmap.width * scale).roundToInt(), (bitmap.height * scale).roundToInt(), true)
        } else {
            bitmap
        }
        val out = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
        if (scaled !== bitmap) scaled.recycle()
        return "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }
}
