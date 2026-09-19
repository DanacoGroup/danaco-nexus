package pl.danaco.nexus.assist

import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService

/**
 * Nexus jako asystent cyfrowy (Ustawienia → Aplikacje domyślne → Asystent cyfrowy).
 * Usługa główna nie nasłuchuje słowa aktywującego – sesję otwiera gest lub przycisk asystenta.
 */
class NexusInteractionService : VoiceInteractionService()

/** Tworzy sesje asystenta (panel Nexusa). */
class NexusSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = NexusSession(this)
}
