package pl.danaco.nexus.config

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Magazyn klucza urządzenia (`nxd_…`) w EncryptedSharedPreferences (klucz główny w Android Keystore).
 * Klucz nigdy nie trafia do logów ani do zwykłych preferencji.
 */
class DeviceKeyStore private constructor(private val prefs: SharedPreferences?) {
    val token: String? get() = prefs?.getString(KEY_TOKEN, null)

    val deviceId: String? get() = prefs?.getString(KEY_ID, null)

    val hasKey: Boolean get() = token != null

    val available: Boolean get() = prefs != null

    fun save(token: String, id: String?): Boolean {
        if (!isValidToken(token)) return false
        return prefs?.edit()?.putString(KEY_TOKEN, token)?.putString(KEY_ID, id)?.commit() ?: false
    }

    fun clear() {
        prefs?.edit()?.clear()?.commit()
    }

    companion object {
        private const val TAG = "NexusKlucz"
        private const val FILE = "nexus_klucz_urzadzenia"
        private const val KEY_TOKEN = "token"
        private const val KEY_ID = "id"
        private val TOKEN_PATTERN = Regex("^nxd_[A-Za-z0-9_-]{20,200}$")

        @Volatile
        private var instance: DeviceKeyStore? = null

        fun get(context: Context): DeviceKeyStore =
            instance ?: synchronized(this) {
                instance ?: DeviceKeyStore(open(context.applicationContext)).also { instance = it }
            }

        /** Format klucza wydawanego przez `POST /api/urzadzenia` (`nxd_` + token_urlsafe). */
        fun isValidToken(token: String?): Boolean = token != null && TOKEN_PATTERN.matches(token)

        private fun open(context: Context): SharedPreferences? =
            try {
                val master = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
                EncryptedSharedPreferences.create(
                    context,
                    FILE,
                    master,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
            } catch (error: Exception) {
                // Uszkodzony magazyn (np. po przywróceniu kopii) – bez zapisu jawnego klucza.
                Log.e(TAG, "Magazyn klucza urządzenia jest niedostępny", error)
                context.deleteSharedPreferences(FILE)
                null
            }
    }
}
