package pl.danaco.nexus.access

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast

/**
 * „Wstaw”: tekst trafia do aktywnego pola w aplikacji pod panelem (usługa dostępności Nexusa).
 * Bez włączonej usługi albo bez pola – tekst jest kopiowany do schowka.
 * Nic nie jest wysyłane – użytkownik sam zatwierdza wiadomość w swojej aplikacji.
 */
object TextInsert {
    private const val DELAY_MS = 450L

    /** Wywoływać po schowaniu panelu – po [DELAY_MS] fokus wraca do pola aplikacji. */
    fun insert(context: Context, text: String) {
        val app = context.applicationContext
        val service = NexusAccessibilityService.instance
        if (service == null) {
            copy(app, text, "Skopiowano. Włącz „Nexus – wstawianie tekstu” w Dostępności, aby wstawiać bezpośrednio.")
            return
        }
        Handler(Looper.getMainLooper()).postDelayed({
            if (!service.insertIntoFocused(text)) copy(app, text, "Nie znaleziono aktywnego pola – skopiowano do schowka.")
        }, DELAY_MS)
    }

    fun copy(context: Context, text: String, message: String = "Skopiowano do schowka.") {
        context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Nexus", text))
        Toast.makeText(context, message, Toast.LENGTH_LONG).show()
    }
}
