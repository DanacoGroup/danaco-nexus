package pl.danaco.nexus.voice

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.web.BridgeMessage

/**
 * Przezroczyste okno uruchamiające rozmowę głosową: prosi o zgodę na mikrofon (i powiadomienia)
 * i startuje usługę, gdy aplikacja jest widoczna – Android wymaga tego dla mikrofonu w tle.
 * Wejścia: kafelek szybkich ustawień, skrót ikony, panel asystenta, języczek, mostek okna głównego.
 */
class VoiceStartActivity : ComponentActivity() {
    private val permissions =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
            if (granted[Manifest.permission.RECORD_AUDIO] == true || hasMic()) {
                startVoice()
            } else {
                Toast.makeText(this, "Rozmowa głosowa wymaga zgody na mikrofon.", Toast.LENGTH_LONG).show()
            }
            finish()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!DeviceKeyStore.get(this).hasKey) {
            Toast.makeText(this, "Najpierw otwórz Nexusa i zaloguj się.", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        if (VoiceService.state.value.running && intent.getBooleanExtra(EXTRA_TOGGLE, false)) {
            VoiceService.stop(this)
            finish()
            return
        }
        val missing = buildList {
            if (!hasMic()) add(Manifest.permission.RECORD_AUDIO)
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(this@VoiceStartActivity, Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        if (missing.isEmpty()) {
            startVoice()
            finish()
        } else if (savedInstanceState == null) {
            permissions.launch(missing.toTypedArray())
        }
    }

    private fun hasMic(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun startVoice() {
        val conversation = intent.getStringExtra(EXTRA_CONVERSATION)?.takeIf { BridgeMessage.isUuid(it) }
        VoiceService.start(this, conversation)
    }

    companion object {
        const val EXTRA_CONVERSATION = "rozmowa"
        const val EXTRA_TOGGLE = "przelacz"

        fun intent(context: Context, conversationId: String? = null, toggle: Boolean = false): Intent =
            Intent(context, VoiceStartActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                .putExtra(EXTRA_CONVERSATION, conversationId)
                .putExtra(EXTRA_TOGGLE, toggle)

        fun start(context: Context, conversationId: String? = null) {
            context.startActivity(intent(context, conversationId))
        }
    }
}
