package pl.danaco.nexus.assist

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.service.voice.VoiceInteractionSession
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import pl.danaco.nexus.R
import pl.danaco.nexus.access.TextInsert
import pl.danaco.nexus.panel.PanelContext
import pl.danaco.nexus.panel.PanelView

/**
 * Sesja asystenta systemowego (przytrzymanie przycisku zasilania / gest asystenta): mały panel
 * na dole ekranu z czatem i rozmową głosową. Tekst ekranu (AssistStructure) i zrzut trafiają
 * do panelu jako `nexus:context` – za zgodą z ustawień asystenta systemu („Użyj tekstu/zrzutu ekranu”).
 */
class NexusSession(context: Context) : VoiceInteractionSession(context), PanelView.Host {
    private val handler = Handler(Looper.getMainLooper())
    private var panel: PanelView? = null
    private var title = ""
    private var url = ""
    private var text = ""
    private var image: String? = null
    private var assistDone = false
    private var screenshotDone = false
    private var contextSent = false
    private val flushContext = Runnable { sendContext() }

    override val screenCapture: (() -> Unit)? = null

    init {
        setTheme(R.style.NexusAssistant)
    }

    override fun onCreateContentView(): View {
        val root = FrameLayout(context)
        val scrim = View(context).apply {
            setBackgroundColor(context.getColor(R.color.nexus_scrim))
            setOnClickListener { hide() }
        }
        root.addView(scrim, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        val view = PanelView(context, this).apply {
            setBackgroundResource(R.drawable.panel_background)
            clipToOutline = true
        }
        val height = (context.resources.displayMetrics.heightPixels * PANEL_HEIGHT).toInt()
        root.addView(view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height, Gravity.BOTTOM))
        panel = view
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        title = ""
        url = ""
        text = ""
        image = null
        contextSent = false
        assistDone = showFlags and SHOW_WITH_ASSIST == 0
        screenshotDone = showFlags and SHOW_WITH_SCREENSHOT == 0
        handler.removeCallbacks(flushContext)
        handler.postDelayed(flushContext, CONTEXT_WAIT_MS)
    }

    override fun onHandleAssist(state: AssistState) {
        val structure = state.assistStructure
        val content = state.assistContent
        if (structure != null) {
            title = ScreenContent.appLabel(context, structure.activityComponent?.packageName)
            text = ScreenContent.text(structure)
        }
        url = content?.webUri?.toString().orEmpty()
        assistDone = true
        if (screenshotDone) sendContext()
    }

    override fun onHandleScreenshot(screenshot: Bitmap?) {
        image = screenshot?.let { ScreenContent.dataUrl(it) }
        screenshotDone = true
        if (assistDone) sendContext()
    }

    private fun sendContext() {
        handler.removeCallbacks(flushContext)
        if (contextSent) return
        if (text.isBlank() && image == null) return
        contextSent = true
        panel?.sendContext(PanelContext("screen", title.ifBlank { "Ekran" }, url, text, image))
    }

    override fun closePanel() = hide()

    override fun insertText(text: String) {
        hide()
        TextInsert.insert(context, text)
    }

    override fun launch(intent: Intent) {
        startAssistantActivity(intent)
    }

    override fun onDestroy() {
        handler.removeCallbacks(flushContext)
        panel?.destroy()
        panel = null
        super.onDestroy()
    }

    private companion object {
        const val PANEL_HEIGHT = 0.72f
        const val CONTEXT_WAIT_MS = 1500L
    }
}
