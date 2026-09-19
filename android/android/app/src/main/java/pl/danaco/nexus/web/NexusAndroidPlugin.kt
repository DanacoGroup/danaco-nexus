package pl.danaco.nexus.web

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Log
import android.webkit.WebView
import android.widget.Toast
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.getcapacitor.Plugin
import com.getcapacitor.annotation.CapacitorPlugin
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.config.NexusConfig
import pl.danaco.nexus.notify.RunWatch
import pl.danaco.nexus.settings.SettingsActivity
import pl.danaco.nexus.sms.SmsActivity
import pl.danaco.nexus.voice.VoiceStartActivity

/**
 * Integracja okna głównego z Androidem. Rejestrowana jako wtyczka Capacitor, bo jej `load()` działa
 * przed pierwszym załadowaniem strony – mostek jest gotowy od pierwszego dokumentu.
 */
@CapacitorPlugin(name = "NexusAndroid")
class NexusAndroidPlugin : Plugin() {
    private var lastKeyRequest = 0L

    override fun load() {
        val webView = bridge.webView
        bridge.setWebViewClient(NexusWebViewClient(bridge))
        webView.setDownloadListener { url, userAgent, disposition, mime, _ ->
            Downloads.enqueue(context, url, userAgent, disposition, mime)
        }
        installBridge(webView)
    }

    @SuppressLint("RequiresFeature")
    private fun installBridge(webView: WebView) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER) ||
            !WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)
        ) {
            Log.w(TAG, "WebView bez WEB_MESSAGE_LISTENER/DOCUMENT_START_SCRIPT – zaktualizuj Android System WebView.")
            return
        }
        val origins = setOf(NexusConfig.ORIGIN)
        WebViewCompat.addWebMessageListener(webView, BRIDGE_NAME, origins) { _, message, origin, mainFrame, reply ->
            if (mainFrame && origin.toString().trimEnd('/') == NexusConfig.ORIGIN) {
                handle(BridgeMessage.parse(message.data), reply)
            }
        }
        WebViewCompat.addDocumentStartJavaScript(webView, script(context, "nexus/most.js"), origins)
    }

    // Wywoływane tylko przez słuchacza zarejestrowanego po sprawdzeniu WEB_MESSAGE_LISTENER.
    @SuppressLint("RequiresFeature")
    private fun handle(message: BridgeMessage?, reply: JavaScriptReplyProxy) {
        val keys = DeviceKeyStore.get(context)
        when (message) {
            is BridgeMessage.Hello -> {
                val now = SystemClock.elapsedRealtime()
                if (keys.available && !keys.hasKey && (lastKeyRequest == 0L || now - lastKeyRequest > KEY_RETRY_MS)) {
                    lastKeyRequest = now
                    reply.postMessage(BridgeMessage.keyRequest(Nexus.deviceName()))
                }
            }
            is BridgeMessage.KeyCreated -> {
                if (keys.save(message.token, message.id)) {
                    Toast.makeText(context, "Aplikacja połączona z Nexusem.", Toast.LENGTH_SHORT).show()
                }
            }
            is BridgeMessage.KeyError -> Log.w(TAG, "Nie udało się utworzyć klucza urządzenia (HTTP ${message.status}).")
            BridgeMessage.KeyNoLogin -> lastKeyRequest = 0L
            is BridgeMessage.RunStarted -> RunWatch.add(context, message.runId, message.conversationId)
            is BridgeMessage.VoiceStart -> VoiceStartActivity.start(context, message.conversationId)
            BridgeMessage.OpenSettings -> open(Intent(context, SettingsActivity::class.java))
            BridgeMessage.OpenSms -> open(Intent(context, SmsActivity::class.java))
            null -> Unit
        }
    }

    private fun open(intent: Intent) {
        activity.startActivity(intent)
    }

    companion object {
        private const val TAG = "NexusMostek"
        const val BRIDGE_NAME = "NexusAndroidBridge"
        private const val KEY_RETRY_MS = 30_000L

        fun script(context: Context, asset: String): String =
            context.assets.open(asset).bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
}
