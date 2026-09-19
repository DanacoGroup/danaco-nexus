package pl.danaco.nexus

import android.app.Application
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import pl.danaco.nexus.notify.Notifications
import pl.danaco.nexus.overlay.EdgeTabService

class NexusApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifications.createChannels(this)
    }
}

/** Po uruchomieniu telefonu (lub aktualizacji aplikacji) przywraca języczek, jeśli był włączony. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            EdgeTabService.startIfEnabled(context)
        }
    }
}
