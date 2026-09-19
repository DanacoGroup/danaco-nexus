package pl.danaco.nexus.panel

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import pl.danaco.nexus.MainActivity
import pl.danaco.nexus.R
import pl.danaco.nexus.access.TextInsert
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.config.NexusConfig
import pl.danaco.nexus.sms.SmsActivity
import pl.danaco.nexus.voice.VoiceService
import pl.danaco.nexus.voice.VoiceStartActivity
import pl.danaco.nexus.web.Downloads
import pl.danaco.nexus.web.NexusAndroidPlugin

/**
 * Panel Nexusa (asystent systemowy i języczek): pasek z rozmową głosową, zrzutem ekranu, SMS
 * i otwarciem aplikacji oraz kompaktowy czat `/?widok=panel` w WebView (umowa trybu osadzonego).
 */
@SuppressLint("ViewConstructor")
class PanelView(
    context: Context,
    private val host: Host,
) : LinearLayout(context) {
    /** Właściciel panelu (sesja asystenta albo usługa języczka). */
    interface Host {
        fun closePanel()

        /** Wstawienie odpowiedzi w pole aktywnej aplikacji (po schowaniu panelu). */
        fun insertText(text: String)

        /** Zrzut ekranu na żądanie (tylko języczek); `null` – przycisk ukryty. */
        val screenCapture: (() -> Unit)?

        /** Uruchomienie okna aplikacji (asystent używa `startAssistantActivity`). */
        fun launch(intent: Intent)
    }

    private val web: WebView
    private val status: TextView
    private val voiceButton: ImageButton
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val pending = mutableListOf<String>()
    private var ready = false

    init {
        orientation = VERTICAL
        LayoutInflater.from(context).inflate(R.layout.panel_nexus, this, true)
        status = findViewById(R.id.panel_status)
        voiceButton = findViewById(R.id.panel_voice)
        web = WebView(context)
        web.setBackgroundColor(Color.parseColor("#212121"))
        findViewById<FrameLayout>(R.id.panel_web).addView(web, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        setupButtons()
        setupWebView()
        scope.launch {
            VoiceService.state.collect { state ->
                status.text = if (state.running) state.error.ifBlank { state.phase.label } else "Asystent"
                voiceButton.isActivated = state.running
                voiceButton.contentDescription = if (state.running) "Zakończ rozmowę głosową" else "Rozmowa głosowa"
            }
        }
    }

    private fun setupButtons() {
        voiceButton.setOnClickListener {
            if (VoiceService.state.value.running) {
                VoiceService.stop(context)
            } else {
                host.launch(VoiceStartActivity.intent(context))
            }
        }
        val screen = findViewById<ImageButton>(R.id.panel_screen)
        val capture = host.screenCapture
        if (capture == null) screen.visibility = GONE else screen.setOnClickListener { capture() }
        val sms = findViewById<ImageButton>(R.id.panel_sms)
        if (!AppSettings(context).sms) {
            sms.visibility = GONE
        } else {
            sms.setOnClickListener {
                host.launch(Intent(context, SmsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                host.closePanel()
            }
        }
        findViewById<ImageButton>(R.id.panel_open).setOnClickListener {
            host.launch(
                Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            )
            host.closePanel()
        }
        findViewById<ImageButton>(R.id.panel_close).setOnClickListener { host.closePanel() }
    }

    @SuppressLint("SetJavaScriptEnabled", "RequiresFeature")
    private fun setupWebView() {
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            allowContentAccess = false
            userAgentString = "$userAgentString NexusAndroid/1 NexusPanel/1"
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                if (NexusConfig.isNexusHost(url.host) && url.scheme == "https") return false
                openExternal(url)
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                // Mikrofon dla trybu rozmowy w panelu – tylko strona Nexusa i tylko przy zgodzie aplikacji.
                val allowed = NexusConfig.isNexusHost(request.origin.host) &&
                    request.resources.all { it == PermissionRequest.RESOURCE_AUDIO_CAPTURE } &&
                    ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                if (allowed) request.grant(request.resources) else request.deny()
            }

            // Panel żyje w oknie usługi (bez aktywności) – systemowe okna dialogowe JS nie mają tu
            // tokenu okna, więc komunikaty są krótkie, a potwierdzenia odsyłane do pełnej aplikacji.
            override fun onJsAlert(view: WebView, url: String, message: String, result: JsResult): Boolean {
                Toast.makeText(context, message, Toast.LENGTH_LONG).show()
                result.confirm()
                return true
            }

            override fun onJsConfirm(view: WebView, url: String, message: String, result: JsResult): Boolean {
                Toast.makeText(context, "Tę czynność potwierdź w aplikacji Nexus.", Toast.LENGTH_LONG).show()
                result.cancel()
                return true
            }

            override fun onJsPrompt(
                view: WebView,
                url: String,
                message: String,
                defaultValue: String?,
                result: JsPromptResult,
            ): Boolean {
                result.cancel()
                return true
            }
        }
        web.setDownloadListener { url, agent, disposition, mime, _ -> Downloads.enqueue(context, url, agent, disposition, mime) }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER) &&
            WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)
        ) {
            val origins = setOf(NexusConfig.ORIGIN)
            WebViewCompat.addWebMessageListener(web, "NexusPanelBridge", origins) { _, message, _, mainFrame, _ ->
                if (mainFrame) onEvent(PanelProtocol.parse(message.data))
            }
            WebViewCompat.addDocumentStartJavaScript(web, NexusAndroidPlugin.script(context, "nexus/panel.js"), origins)
        } else {
            Log.w(TAG, "WebView bez obsługi mostka panelu – zaktualizuj Android System WebView.")
        }
        web.loadUrl(NexusConfig.PANEL_URL)
    }

    private fun onEvent(event: PanelEvent?) {
        when (event) {
            PanelEvent.Ready -> {
                ready = true
                DeviceKeyStore.get(context).token?.let { run(PanelProtocol.auth(it)) }
                pending.forEach(::run)
                pending.clear()
            }
            is PanelEvent.Insert -> host.insertText(event.text)
            is PanelEvent.Copy -> TextInsert.copy(context, event.text)
            null -> Unit
        }
    }

    /** Kontekst ekranu lub strony dołączany do następnej wiadomości w panelu. */
    fun sendContext(context: PanelContext) = post(PanelProtocol.context(context))

    fun sendPrompt(text: String, send: Boolean) = post(PanelProtocol.prompt(text, send))

    private fun post(message: String) {
        if (ready) run(message) else pending += message
    }

    private fun run(message: String) {
        web.evaluateJavascript(PanelProtocol.script(message), null)
    }

    private fun openExternal(url: Uri) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            host.closePanel()
        } catch (_: Exception) {
            Toast.makeText(context, "Nie można otworzyć odnośnika.", Toast.LENGTH_SHORT).show()
        }
    }

    fun destroy() {
        scope.cancel()
        web.stopLoading()
        web.destroy()
    }

    private companion object {
        const val TAG = "NexusPanel"
    }
}
