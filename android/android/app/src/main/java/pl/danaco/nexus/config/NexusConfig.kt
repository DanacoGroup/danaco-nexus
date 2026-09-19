package pl.danaco.nexus.config

import android.net.Uri
import pl.danaco.nexus.BuildConfig

/** Adresy serwera Nexusa używane przez aplikację. */
object NexusConfig {
    val BASE_URL: String = BuildConfig.NEXUS_URL.trimEnd('/')

    /** Kompaktowy czat do osadzania (tryb osadzony, umowa `?widok=panel`). */
    val PANEL_URL: String = "$BASE_URL/?widok=panel"

    val ORIGIN: String = BASE_URL

    val HOST: String = Uri.parse(BASE_URL).host ?: "danaco-nexus.pl"

    /** Czy adres należy do Nexusa (aplikacja, API, chmura) – wtedy zostaje w oknie aplikacji. */
    fun isNexusHost(host: String?): Boolean {
        if (host == null) return false
        val normalized = host.lowercase()
        return normalized == HOST || normalized.endsWith(".$HOST")
    }
}
