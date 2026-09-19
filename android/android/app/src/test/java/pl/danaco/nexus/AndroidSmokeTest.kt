package pl.danaco.nexus

import android.app.Application
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageInfo
import android.view.View
import android.widget.TextView
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowWebView
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.overlay.EdgeTabService
import pl.danaco.nexus.panel.PanelView
import pl.danaco.nexus.settings.SettingsActivity
import pl.danaco.nexus.sms.SmsActivity
import pl.danaco.nexus.voice.VoiceStartActivity

/**
 * Testy dymne okien i usług na JVM (Robolectric): zasoby, motywy i manifest ładują się bez błędów,
 * a funkcje wymagające zgód nie startują bez nich. Nie zastępują testu na fizycznym telefonie.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = NexusApplication::class)
class AndroidSmokeTest {
    private val app: Application get() = ApplicationProvider.getApplicationContext()

    private fun texts(view: View): List<String> {
        val result = mutableListOf<String>()
        fun walk(node: View) {
            if (node is TextView) result += node.text.toString()
            if (node is android.view.ViewGroup) for (index in 0 until node.childCount) walk(node.getChildAt(index))
        }
        walk(view)
        return result
    }

    @Test
    fun `okno glowne laduje nexusa z wtyczka mostka`() {
        ShadowWebView.setCurrentWebViewPackage(
            PackageInfo().apply {
                packageName = "com.google.android.webview"
                versionName = "140.0.7339.0"
            },
        )
        val activity = Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val webView = activity.bridge.webView
        assertEquals("https://danaco-nexus.pl", activity.bridge.serverUrl)
        assertTrue(shadowOf(webView).lastLoadedUrl.startsWith("https://danaco-nexus.pl"))
        assertTrue(shadowOf(webView).webViewClient is pl.danaco.nexus.web.NexusWebViewClient)
        assertNotNull(activity.bridge.getPlugin("NexusAndroid"))
    }

    @Test
    fun `kanaly powiadomien`() {
        val manager = app.getSystemService(NotificationManager::class.java)
        val channels = manager.notificationChannels.map { it.id }.toSet()
        assertEquals(setOf("rozmowa", "zadania", "jezyczek"), channels)
    }

    @Test
    fun `ustawienia pokazuja wszystkie moduly`() {
        val activity = Robolectric.buildActivity(SettingsActivity::class.java).setup().get()
        val shown = texts(activity.window.decorView)
        for (section in listOf("Połączenie z Nexusem", "Rozmowa głosowa w tle", "Asystent cyfrowy", "Języczek przy krawędzi", "Odczyt tekstu i „Wstaw”", "SMS – szkice odpowiedzi", "Powiadomienia")) {
            assertTrue("brak sekcji $section", section in shown)
        }
    }

    @Test
    fun `sms bez zgody pokazuje wyjasnienie`() {
        AppSettings(app).sms = true
        val activity = Robolectric.buildActivity(SmsActivity::class.java).setup().get()
        assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.sms_consent).visibility)
        assertEquals(View.GONE, activity.findViewById<View>(R.id.sms_threads).visibility)
    }

    @Test
    fun `sms wylaczony w ustawieniach zamyka okno`() {
        AppSettings(app).sms = false
        val activity = Robolectric.buildActivity(SmsActivity::class.java).setup().get()
        assertTrue(activity.isFinishing)
    }

    @Test
    fun `rozmowa bez polaczenia z nexusem nie startuje uslugi`() {
        val activity = Robolectric.buildActivity(VoiceStartActivity::class.java, VoiceStartActivity.intent(app)).setup().get()
        assertTrue(activity.isFinishing)
        assertNull(shadowOf(app).nextStartedService)
    }

    @Test
    fun `jezyczek wylaczony nie uruchamia uslugi`() {
        AppSettings(app).edgeTab = false
        EdgeTabService.startIfEnabled(app)
        assertNull(shadowOf(app).nextStartedService)
    }

    @Test
    fun `panel buduje pasek i czat`() {
        val activity = Robolectric.buildActivity(SettingsActivity::class.java).setup().get()
        var closed = false
        val host = object : PanelView.Host {
            override fun closePanel() {
                closed = true
            }

            override fun insertText(text: String) = Unit

            override val screenCapture: (() -> Unit)? = null

            override fun launch(intent: Intent) = Unit
        }
        val panel = PanelView(activity, host)
        assertNotNull(panel.findViewById(R.id.panel_voice))
        assertEquals(View.GONE, panel.findViewById<View>(R.id.panel_screen).visibility)
        panel.findViewById<View>(R.id.panel_close).performClick()
        assertTrue(closed)
        panel.destroy()
    }
}
