package pl.danaco.nexus

import android.content.Context
import android.os.Build
import pl.danaco.nexus.api.ApiException
import pl.danaco.nexus.api.NexusApi
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.config.NexusConfig

/** Wspólne obiekty aplikacji: klient API z kluczem urządzenia. */
object Nexus {
    @Volatile
    private var api: NexusApi? = null

    fun api(context: Context): NexusApi =
        api ?: synchronized(this) {
            api ?: run {
                val keys = DeviceKeyStore.get(context)
                NexusApi(NexusConfig.BASE_URL, { keys.token }).also { api = it }
            }
        }

    /** Nazwa urządzenia na liście kluczy w Nexusie. */
    fun deviceName(): String = "Android – ${Build.MANUFACTURER} ${Build.MODEL}".trim().take(100)

    /**
     * Klucz odrzucony przez serwer (cofnięty na stronie „Urządzenia”) – usuwany lokalnie;
     * nowy powstanie po otwarciu aplikacji w zalogowanym oknie.
     */
    fun handleFailure(context: Context, error: Throwable) {
        if (error is ApiException && error.unauthorized) {
            val keys = DeviceKeyStore.get(context)
            if (keys.hasKey) keys.clear()
        }
    }

    /** Komunikat błędu dla użytkownika. */
    fun describe(error: Throwable): String =
        when {
            error is ApiException && error.unauthorized ->
                "Aplikacja nie jest połączona z Nexusem. Otwórz Nexusa i zaloguj się."
            error is ApiException -> error.message ?: "Błąd serwera."
            else -> "Brak połączenia z Nexusem."
        }
}
