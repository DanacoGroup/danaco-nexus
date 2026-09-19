package pl.danaco.nexus.config

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/** Ustawienia modułów aplikacji (wszystko wyłączalne; domyślnie wyłączone funkcje wymagające zgód). */
class AppSettings(context: Context) {
    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences("nexus_ustawienia", Context.MODE_PRIVATE)

    /** Języczek przy krawędzi ekranu (nakładka). */
    var edgeTab: Boolean
        get() = prefs.getBoolean("jezyczek", false)
        set(value) = prefs.edit { putBoolean("jezyczek", value) }

    /** Zrzut ekranu (MediaProjection) dla języczka – za każdym razem za zgodą systemową. */
    var screenCapture: Boolean
        get() = prefs.getBoolean("zrzut_ekranu", false)
        set(value) = prefs.edit { putBoolean("zrzut_ekranu", value) }

    /** Szkice odpowiedzi na SMS (odczyt wiadomości na żądanie). */
    var sms: Boolean
        get() = prefs.getBoolean("sms", false)
        set(value) = prefs.edit { putBoolean("sms", value) }

    /** Powiadomienie o zakończeniu zadań rozpoczętych w aplikacji. */
    var runNotifications: Boolean
        get() = prefs.getBoolean("powiadomienia_zadan", true)
        set(value) = prefs.edit { putBoolean("powiadomienia_zadan", value) }

    /** Wybrany głos rozmowy (pusty – domyślny głos serwera). */
    var voice: String
        get() = prefs.getString("glos", "").orEmpty()
        set(value) = prefs.edit { putString("glos", value) }

    /** Położenie języczka (część wysokości ekranu 0..1). */
    var edgeTabPosition: Float
        get() = prefs.getFloat("jezyczek_pozycja", 0.35f)
        set(value) = prefs.edit { putFloat("jezyczek_pozycja", value.coerceIn(0.05f, 0.9f)) }
}
