package pl.danaco.nexus.notify

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import pl.danaco.nexus.MainActivity
import pl.danaco.nexus.R

/** Kanały i pomocnicze funkcje powiadomień. */
object Notifications {
    const val CHANNEL_VOICE = "rozmowa"
    const val CHANNEL_RUNS = "zadania"
    const val CHANNEL_OVERLAY = "jezyczek"

    const val ID_VOICE = 1001
    const val ID_OVERLAY = 1002
    private const val ID_RUN_BASE = 2000
    const val ID_ACCOUNT = 1003

    fun createChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(CHANNEL_VOICE, "Rozmowa głosowa", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Nexus słucha w tle – przyciski Wstrzymaj i Zakończ."
                    setShowBadge(false)
                },
                NotificationChannel(CHANNEL_RUNS, "Zakończone zadania", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Informacja, że Nexus skończył zadanie rozpoczęte w aplikacji."
                },
                NotificationChannel(CHANNEL_OVERLAY, "Języczek przy krawędzi", NotificationManager.IMPORTANCE_MIN).apply {
                    description = "Stałe powiadomienie usługi języczka (wymagane przez system)."
                    setShowBadge(false)
                },
            ),
        )
    }

    fun canPost(context: Context): Boolean {
        // Zgoda POST_NOTIFICATIONS istnieje od Androida 13; wcześniej wystarczy włączenie w ustawieniach.
        val permitted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        return permitted && NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    /** Otwiera aplikację (opcjonalnie na rozmowie o podanym identyfikatorze). */
    fun openAppIntent(context: Context, conversationId: String? = null): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        if (conversationId != null) intent.putExtra(MainActivity.EXTRA_CONVERSATION, conversationId)
        return PendingIntent.getActivity(
            context,
            conversationId?.hashCode() ?: 0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    /** Powiadomienie o zakończonym zadaniu. */
    fun runFinished(context: Context, runId: String, conversationId: String, title: String, status: String) {
        if (!canPost(context)) return
        val text = when (status) {
            "done" -> "Gotowe – dotknij, aby zobaczyć odpowiedź."
            "cancelled" -> "Zadanie zostało anulowane."
            else -> "Zadanie zakończyło się błędem."
        }
        val notification = NotificationCompat.Builder(context, CHANNEL_RUNS)
            .setSmallIcon(R.drawable.ic_stat_nexus)
            .setContentTitle(title.ifBlank { "Nexus" })
            .setContentText(text)
            .setContentIntent(openAppIntent(context, conversationId))
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(runId, ID_RUN_BASE, notification)
        } catch (_: SecurityException) {
            // Zgoda na powiadomienia cofnięta w międzyczasie.
        }
    }
}
