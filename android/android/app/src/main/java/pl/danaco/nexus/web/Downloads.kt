package pl.danaco.nexus.web

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.widget.Toast
import pl.danaco.nexus.config.NexusConfig

/** Pobieranie plików z okna aplikacji przez systemowy DownloadManager (folder Pobrane). */
object Downloads {
    fun enqueue(context: Context, url: String, userAgent: String?, contentDisposition: String?, mimeType: String?) {
        val uri = Uri.parse(url)
        if (uri.scheme != "https" && uri.scheme != "http") {
            Toast.makeText(context, "Tego pliku nie można pobrać w aplikacji.", Toast.LENGTH_LONG).show()
            return
        }
        val name = URLUtil.guessFileName(url, contentDisposition, mimeType)
        val request = DownloadManager.Request(uri)
            .setTitle(name)
            .setDescription("Nexus – pobieranie")
            .setMimeType(mimeType)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
        if (!userAgent.isNullOrBlank()) request.addRequestHeader("User-Agent", userAgent)
        // Ciasteczko sesji tylko dla adresów Nexusa – nigdy dla obcych serwerów.
        if (NexusConfig.isNexusHost(uri.host)) {
            CookieManager.getInstance().getCookie(url)?.let { request.addRequestHeader("Cookie", it) }
        }
        try {
            context.getSystemService(DownloadManager::class.java).enqueue(request)
            Toast.makeText(context, "Pobieranie: $name", Toast.LENGTH_SHORT).show()
        } catch (error: IllegalArgumentException) {
            Toast.makeText(context, "Nie udało się rozpocząć pobierania.", Toast.LENGTH_LONG).show()
        }
    }
}
