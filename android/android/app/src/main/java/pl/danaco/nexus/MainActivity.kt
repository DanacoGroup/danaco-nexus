package pl.danaco.nexus

import android.content.Intent
import android.os.Bundle
import androidx.activity.OnBackPressedCallback
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.lifecycleScope
import com.getcapacitor.BridgeActivity
import kotlinx.coroutines.launch
import pl.danaco.nexus.api.ApiException
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.config.NexusConfig
import pl.danaco.nexus.notify.RunWatch
import pl.danaco.nexus.overlay.EdgeTabService
import pl.danaco.nexus.web.BridgeMessage
import pl.danaco.nexus.web.NexusAndroidPlugin

/** Główne okno: aplikacja https://danaco-nexus.pl w WebView (Capacitor) z mostkiem natywnym. */
class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        registerPlugin(NexusAndroidPlugin::class.java)
        super.onCreate(savedInstanceState)
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    val webView = bridge?.webView
                    if (webView != null && webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        moveTaskToBack(true)
                    }
                }
            },
        )
        if (savedInstanceState == null) openFromIntent(intent)
        verifyDeviceKey()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        openFromIntent(intent)
    }

    override fun onStart() {
        super.onStart()
        RunWatch.cancel(this)
        EdgeTabService.startIfEnabled(this)
    }

    override fun onStop() {
        super.onStop()
        RunWatch.schedule(this)
    }

    private fun openFromIntent(intent: Intent?) {
        val link = intent?.data?.takeIf { intent.action == Intent.ACTION_VIEW && NexusConfig.isNexusHost(it.host) }
        val conversation = intent?.getStringExtra(EXTRA_CONVERSATION)
            ?: link?.path?.removePrefix("/c/")?.trimEnd('/')
        val path = when {
            BridgeMessage.isUuid(conversation) -> "/c/$conversation"
            intent?.action == ACTION_NEW_CONVERSATION -> "/"
            else -> return
        }
        intent?.removeExtra(EXTRA_CONVERSATION)
        bridge?.webView?.loadUrl(NexusConfig.BASE_URL + path)
    }

    /** Klucz cofnięty na serwerze jest usuwany – mostek poprosi o nowy przy następnym wejściu. */
    private fun verifyDeviceKey() {
        if (!DeviceKeyStore.get(this).hasKey) return
        lifecycleScope.launch {
            try {
                Nexus.api(this@MainActivity).me()
            } catch (error: ApiException) {
                Nexus.handleFailure(this@MainActivity, error)
            } catch (_: Exception) {
                // Brak sieci – sprawdzenie przy następnym uruchomieniu.
            }
        }
    }

    companion object {
        const val EXTRA_CONVERSATION = "pl.danaco.nexus.ROZMOWA"
        const val ACTION_NEW_CONVERSATION = "pl.danaco.nexus.NOWA_ROZMOWA"
    }
}
