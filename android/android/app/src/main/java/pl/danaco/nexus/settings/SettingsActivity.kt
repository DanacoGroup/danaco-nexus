package pl.danaco.nexus.settings

import android.Manifest
import android.app.role.RoleManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import pl.danaco.nexus.BuildConfig
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.R
import pl.danaco.nexus.access.NexusAccessibilityService
import pl.danaco.nexus.api.Voice
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.config.DeviceKeyStore
import pl.danaco.nexus.overlay.EdgeTabService
import pl.danaco.nexus.sms.SmsActivity
import pl.danaco.nexus.voice.VoiceStartActivity

/**
 * Ustawienia modułów Androida. Każda funkcja wymagająca uprawnień jest domyślnie wyłączona,
 * a przed prośbą systemową użytkownik widzi wyjaśnienie, co Nexus zrobi z danym dostępem.
 */
class SettingsActivity : AppCompatActivity() {
    private lateinit var settings: AppSettings
    private lateinit var content: LinearLayout
    private var pendingOverlay = false

    private val smsPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        settings.sms = granted
        render()
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        settings.runNotifications = granted
        render()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        settings = AppSettings(this)
        content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(8), dp(16), dp(24))
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            fitsSystemWindows = true
            setBackgroundColor(getColor(R.color.nexus_app))
        }
        root.addView(header())
        root.addView(ScrollView(this).apply { addView(content) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        if (pendingOverlay && Settings.canDrawOverlays(this)) {
            settings.edgeTab = true
            EdgeTabService.startIfEnabled(this)
        }
        pendingOverlay = false
        render()
    }

    private fun render() {
        content.removeAllViews()
        val keys = DeviceKeyStore.get(this)

        section("Połączenie z Nexusem")
        body(
            if (keys.hasKey) {
                "Aplikacja jest połączona kluczem urządzenia. Klucz można cofnąć w Nexusie na stronie „Urządzenia”."
            } else {
                "Aplikacja nie jest jeszcze połączona. Otwórz Nexusa i zaloguj się – klucz urządzenia powstanie automatycznie."
            },
        )
        if (keys.hasKey) {
            button("Odłącz to urządzenie") {
                confirm(
                    "Odłączyć urządzenie?",
                    "Klucz zostanie usunięty z telefonu. Rozmowa w tle, asystent i SMS przestaną działać do ponownego " +
                        "zalogowania. Aby unieważnić klucz także na serwerze, cofnij go na stronie „Urządzenia”.",
                ) {
                    keys.clear()
                    render()
                }
            }
        }

        section("Rozmowa głosowa w tle")
        body(
            "Nexus słucha, rozpoznaje mowę na serwerze i czyta odpowiedzi – także przy wygaszonym ekranie. " +
                "Podczas rozmowy widać powiadomienie „Nexus słucha” z przyciskami Wstrzymaj i Zakończ. " +
                "Rozmowę uruchomisz też kafelkiem w szybkich ustawieniach i skrótem na ikonie aplikacji.",
        )
        button("Rozpocznij rozmowę") { VoiceStartActivity.start(this) }
        voicePicker()

        section("Asystent cyfrowy")
        body(
            "Po wybraniu Nexusa jako asystenta przytrzymanie przycisku zasilania (lub gest asystenta) otwiera panel " +
                "Nexusa nad bieżącą aplikacją. Tekst i zrzut ekranu trafiają do Nexusa tylko wtedy, gdy włączysz " +
                "„Użyj tekstu z ekranu” i „Użyj zrzutu ekranu” w ustawieniach asystenta systemu.",
        )
        status(if (isAssistant()) "Nexus jest asystentem cyfrowym." else "Nexus nie jest jeszcze asystentem cyfrowym.")
        button("Ustawienia asystenta cyfrowego") { openAssistantSettings() }

        section("Języczek przy krawędzi")
        switch("Pokaż języczek", settings.edgeTab) { enabled -> toggleEdgeTab(enabled) }
        body("Mały uchwyt przy prawej krawędzi ekranu otwiera panel Nexusa nad dowolną aplikacją (wymaga zgody „Wyświetlanie nad innymi aplikacjami”).")
        switch("Zrzut ekranu dla języczka", settings.screenCapture) { enabled ->
            if (enabled) {
                confirm(
                    "Zrzut ekranu",
                    "Po naciśnięciu przycisku ekranu w panelu Android zapyta o zgodę na przechwycenie ekranu – za każdym razem. " +
                        "Nexus zrobi jeden zrzut, dołączy go do wiadomości w panelu i od razu zakończy przechwytywanie.",
                    onCancel = { render() },
                ) {
                    settings.screenCapture = true
                    restartEdgeTab()
                }
            } else {
                settings.screenCapture = false
                restartEdgeTab()
            }
        }

        section("Odczyt tekstu i „Wstaw”")
        body(
            "Opcjonalna usługa dostępności „Nexus – wstawianie tekstu”: po Twoim poleceniu odczytuje tekst aplikacji " +
                "pod panelem i wstawia odpowiedź w aktywne pole. Nie działa w tle, nie wysyła wiadomości i nie klika przycisków.",
        )
        status(if (accessibilityEnabled()) "Usługa jest włączona." else "Usługa jest wyłączona.")
        button(if (accessibilityEnabled()) "Wyłącz w ustawieniach Dostępności" else "Włącz w ustawieniach Dostępności") {
            confirm(
                "Usługa dostępności",
                "Otworzy się systemowa lista usług dostępności. Wybierz „Nexus – wstawianie tekstu” i zmień jej stan. " +
                    "Android pokaże pełną informację o zakresie dostępu.",
            ) { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        }

        section("SMS – szkice odpowiedzi")
        switch("Szkice odpowiedzi na SMS", settings.sms && hasPermission(Manifest.permission.READ_SMS)) { enabled -> toggleSms(enabled) }
        body(
            "Na Twoje żądanie Nexus odczytuje ostatnie wiadomości wybranego wątku i przygotowuje szkic odpowiedzi. " +
                "Szkic możesz wstawić, skopiować albo otworzyć w Wiadomościach – Nexus nigdy nie wysyła SMS-ów sam.",
        )
        if (settings.sms && hasPermission(Manifest.permission.READ_SMS)) {
            button("Otwórz szkice SMS") { startActivity(Intent(this, SmsActivity::class.java)) }
        }

        section("Powiadomienia")
        switch("Powiadom o zakończonych zadaniach", settings.runNotifications && notificationsAllowed()) { enabled ->
            if (enabled && !notificationsAllowed() && Build.VERSION.SDK_INT >= 33) {
                notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                settings.runNotifications = enabled
            }
        }
        body("Gdy zlecisz zadanie i wyjdziesz z aplikacji, Nexus powiadomi Cię o jego zakończeniu.")

        section("O aplikacji")
        body("Nexus dla Androida ${BuildConfig.VERSION_NAME} · serwer ${BuildConfig.NEXUS_URL}")
    }

    // --- akcje -----------------------------------------------------------------------------

    private fun toggleEdgeTab(enabled: Boolean) {
        if (!enabled) {
            settings.edgeTab = false
            EdgeTabService.stop(this)
            render()
            return
        }
        if (Settings.canDrawOverlays(this)) {
            settings.edgeTab = true
            EdgeTabService.startIfEnabled(this)
            render()
            return
        }
        confirm(
            "Wyświetlanie nad innymi aplikacjami",
            "Języczek i panel Nexusa są wyświetlane nad innymi aplikacjami. Na następnym ekranie włącz tę zgodę dla Nexusa.",
            onCancel = { render() },
        ) {
            pendingOverlay = true
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        }
    }

    private fun restartEdgeTab() {
        EdgeTabService.stop(this)
        EdgeTabService.startIfEnabled(this)
        render()
    }

    private fun toggleSms(enabled: Boolean) {
        if (!enabled) {
            settings.sms = false
            render()
            return
        }
        confirm(
            "Odczyt SMS",
            "Nexus odczyta ostatnie wiadomości tylko wtedy, gdy otworzysz szkice SMS i wybierzesz wątek. " +
                "Treść wybranego wątku zostanie przesłana do Twojego serwera Nexusa, aby przygotować szkic. Nic nie jest wysyłane automatycznie.",
            onCancel = { render() },
        ) {
            if (hasPermission(Manifest.permission.READ_SMS)) {
                settings.sms = true
                render()
            } else {
                smsPermission.launch(Manifest.permission.READ_SMS)
            }
        }
    }

    private fun openAssistantSettings() {
        val candidates = listOf(
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS),
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS),
            Intent(Settings.ACTION_SETTINGS),
        )
        for (intent in candidates) {
            try {
                startActivity(intent)
                return
            } catch (_: Exception) {
                // Kolejna próba – producenci różnie nazywają ekran asystenta.
            }
        }
    }

    private fun isAssistant(): Boolean =
        getSystemService(RoleManager::class.java)?.isRoleHeld(RoleManager.ROLE_ASSISTANT) == true

    private fun accessibilityEnabled(): Boolean {
        if (NexusAccessibilityService.instance != null) return true
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        val component = ComponentName(this, NexusAccessibilityService::class.java).flattenToString()
        val splitter = TextUtils.SimpleStringSplitter(':').apply { setString(enabled) }
        return splitter.any { it.equals(component, ignoreCase = true) }
    }

    private fun hasPermission(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    private fun notificationsAllowed() =
        Build.VERSION.SDK_INT < 33 || hasPermission(Manifest.permission.POST_NOTIFICATIONS)

    private fun voicePicker() {
        if (!DeviceKeyStore.get(this).hasKey) return
        val spinner = Spinner(this)
        content.addView(spinner, LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(8) })
        lifecycleScope.launch {
            val voices: List<Voice> = try {
                Nexus.api(this@SettingsActivity).voiceConfig().voices
            } catch (error: Exception) {
                Nexus.handleFailure(this@SettingsActivity, error)
                emptyList()
            }
            if (voices.isEmpty()) {
                spinner.visibility = View.GONE
                return@launch
            }
            val options = listOf(Voice("", "Głos domyślny serwera")) + voices
            spinner.adapter = ArrayAdapter(this@SettingsActivity, android.R.layout.simple_spinner_dropdown_item, options.map { "Głos: ${it.name}" })
            spinner.setSelection(options.indexOfFirst { it.id == settings.voice }.coerceAtLeast(0))
            spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    settings.voice = options[position].id
                }

                override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            }
        }
    }

    // --- elementy interfejsu ---------------------------------------------------------------

    private fun header(): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(getColor(R.color.nexus_side))
            setPadding(dp(4), 0, dp(16), 0)
            minimumHeight = dp(56)
            addView(
                android.widget.ImageButton(this@SettingsActivity, null, 0, R.style.NexusIconButton).apply {
                    setImageResource(R.drawable.ic_back)
                    contentDescription = getString(R.string.back)
                    setOnClickListener { finish() }
                },
                LinearLayout.LayoutParams(dp(44), dp(44)),
            )
            addView(
                TextView(this@SettingsActivity).apply {
                    text = getString(R.string.settings_title)
                    setTextColor(getColor(R.color.nexus_fg))
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
                    paint.isFakeBoldText = true
                    setPadding(dp(8), 0, 0, 0)
                },
            )
        }

    private fun section(title: String) {
        content.addView(
            TextView(this, null, 0, R.style.NexusSectionTitle).apply { text = title },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(24) },
        )
    }

    private fun body(text: String) {
        content.addView(
            TextView(this, null, 0, R.style.NexusBody).apply { this.text = text },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(6) },
        )
    }

    private fun status(text: String) {
        content.addView(
            TextView(this, null, 0, R.style.NexusBody).apply {
                this.text = text
                setTextColor(getColor(R.color.nexus_fg))
            },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) },
        )
    }

    private fun button(label: String, action: () -> Unit) {
        content.addView(
            Button(this, null, 0, R.style.NexusButton).apply {
                text = label
                setOnClickListener { action() }
            },
            LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(10) },
        )
    }

    private fun switch(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
        content.addView(
            SwitchCompat(this).apply {
                text = label
                isChecked = checked
                setTextColor(getColor(R.color.nexus_fg))
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
                minHeight = dp(48)
                setOnCheckedChangeListener { _, value -> onChange(value) }
            },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) },
        )
    }

    private fun confirm(title: String, message: String, onCancel: () -> Unit = {}, onAccept: () -> Unit) {
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("Dalej") { _, _ -> onAccept() }
            .setNegativeButton("Anuluj") { _, _ -> onCancel() }
            .setOnCancelListener { onCancel() }
            .show()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
