package pl.danaco.nexus.notify

import android.content.Context
import androidx.core.content.edit
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.api.ApiException
import pl.danaco.nexus.config.AppSettings

/**
 * Lokalne powiadomienia o zakończeniu zadań rozpoczętych w oknie aplikacji (WebView nie obsługuje
 * Web Push). Mostek zgłasza nowe zadania; po zejściu aplikacji w tło WorkManager sprawdza ich stan
 * co [CHECK_DELAY_S] s, najdłużej [MAX_WATCH_MS] od rozpoczęcia.
 */
object RunWatch {
    private const val PREFS = "nexus_zadania"
    private const val KEY = "obserwowane"
    private const val WORK = "nexus-obserwacja-zadan"
    const val CHECK_DELAY_S = 30L
    const val MAX_WATCH_MS = 3 * 60 * 60 * 1000L

    data class Entry(val runId: String, val conversationId: String, val startedAt: Long)

    fun add(context: Context, runId: String, conversationId: String) {
        val entries = load(context).filterNot { it.runId == runId } + Entry(runId, conversationId, System.currentTimeMillis())
        save(context, entries.takeLast(20))
    }

    fun load(context: Context): List<Entry> {
        val raw = prefs(context).getString(KEY, "[]") ?: "[]"
        return try {
            val array = JSONArray(raw)
            (0 until array.length()).map { index ->
                val item = array.getJSONObject(index)
                Entry(item.getString("run"), item.getString("conversation"), item.getLong("started"))
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun save(context: Context, entries: List<Entry>) {
        val array = JSONArray()
        entries.forEach {
            array.put(JSONObject().put("run", it.runId).put("conversation", it.conversationId).put("started", it.startedAt))
        }
        prefs(context).edit { putString(KEY, array.toString()) }
    }

    /** Aplikacja zeszła w tło – zaczyna obserwację (jeśli są zadania i powiadomienia są włączone). */
    fun schedule(context: Context, delaySeconds: Long = CHECK_DELAY_S) {
        if (!AppSettings(context).runNotifications || load(context).isEmpty()) return
        val request = OneTimeWorkRequestBuilder<RunWatchWorker>()
            .setInitialDelay(delaySeconds, TimeUnit.SECONDS)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(WORK, ExistingWorkPolicy.REPLACE, request)
    }

    /** Aplikacja na pierwszym planie – użytkownik widzi wyniki sam. */
    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK)
    }

    private fun prefs(context: Context) = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}

class RunWatchWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val context = applicationContext
        val api = Nexus.api(context)
        val now = System.currentTimeMillis()
        val remaining = mutableListOf<RunWatch.Entry>()
        val titles = mutableMapOf<String, String>()
        for (entry in RunWatch.load(context)) {
            if (now - entry.startedAt > RunWatch.MAX_WATCH_MS) continue
            val status = try {
                api.runStatus(entry.runId)
            } catch (error: ApiException) {
                Nexus.handleFailure(context, error)
                if (error.status == 404 || error.unauthorized) continue
                remaining += entry
                continue
            } catch (_: Exception) {
                remaining += entry
                continue
            }
            if (status.active) {
                remaining += entry
                continue
            }
            if (titles.isEmpty()) {
                runCatching { api.listConversations() }.getOrNull()?.forEach { titles[it.id] = it.title }
            }
            Notifications.runFinished(context, entry.runId, entry.conversationId, titles[entry.conversationId].orEmpty(), status.status)
        }
        RunWatch.save(context, remaining)
        if (remaining.isNotEmpty()) RunWatch.schedule(context)
        return Result.success()
    }
}
