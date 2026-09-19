package pl.danaco.nexus.overlay

import android.annotation.SuppressLint
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.DisplayMetrics
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import kotlin.math.abs
import kotlin.math.min
import kotlin.math.roundToInt
import pl.danaco.nexus.R
import pl.danaco.nexus.access.NexusAccessibilityService
import pl.danaco.nexus.access.TextInsert
import pl.danaco.nexus.assist.ScreenContent
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.notify.Notifications
import pl.danaco.nexus.panel.PanelContext
import pl.danaco.nexus.panel.PanelView
import pl.danaco.nexus.settings.SettingsActivity

/**
 * Języczek przy prawej krawędzi ekranu (nakładka SYSTEM_ALERT_WINDOW): dotknięcie lub przeciągnięcie
 * w lewo otwiera panel Nexusa nad dowolną aplikacją; przeciąganie w pionie zmienia położenie.
 * Zawartość ekranu: zrzut przez MediaProjection (zgoda systemowa za każdym razem) i/lub tekst
 * z usługi dostępności – wyłącznie po naciśnięciu przycisku ekranu w panelu.
 */
class EdgeTabService : Service(), PanelView.Host {
    private lateinit var windows: WindowManager
    private lateinit var settings: AppSettings
    private var tab: View? = null
    private var tabParams: WindowManager.LayoutParams? = null
    private var panelWindow: FrameLayout? = null
    private var panel: PanelView? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windows = getSystemService(WindowManager::class.java)
        settings = AppSettings(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!Settings.canDrawOverlays(this) || !settings.edgeTab) {
            stopSelf()
            return START_NOT_STICKY
        }
        try {
            ServiceCompat.startForeground(this, Notifications.ID_OVERLAY, notification(), overlayType())
        } catch (error: Exception) {
            Log.w(TAG, "Nie można uruchomić języczka", error)
            stopSelf()
            return START_NOT_STICKY
        }
        when (intent?.action) {
            ACTION_SHOW_PANEL -> openPanel()
            ACTION_CAPTURE -> {
                val data = intent.parcelableIntent(EXTRA_DATA)
                val code = intent.getIntExtra(EXTRA_CODE, 0)
                if (data != null) capture(code, data) else openPanel()
            }
            else -> showTab()
        }
        return START_STICKY
    }

    // --- języczek --------------------------------------------------------------------------

    @SuppressLint("ClickableViewAccessibility")
    private fun showTab() {
        if (tab != null) return
        val density = resources.displayMetrics.density
        val view = View(this).apply {
            setBackgroundResource(R.drawable.edge_tab)
            contentDescription = getString(R.string.edge_tab_description)
            setOnClickListener { openPanel() }
        }
        val params = WindowManager.LayoutParams(
            (TAB_WIDTH_DP * density).roundToInt(),
            (TAB_HEIGHT_DP * density).roundToInt(),
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            y = (screenHeight() * settings.edgeTabPosition).roundToInt()
        }
        view.setOnTouchListener(TabTouch(params))
        windows.addView(view, params)
        tab = view
        tabParams = params
    }

    /** Dotknięcie – panel; przeciągnięcie w lewo – panel; w pionie – przesunięcie języczka. */
    private inner class TabTouch(private val params: WindowManager.LayoutParams) : View.OnTouchListener {
        private val slop = ViewConfiguration.get(this@EdgeTabService).scaledTouchSlop
        private var downX = 0f
        private var downY = 0f
        private var startY = 0
        private var dragging = false

        override fun onTouch(view: View, event: MotionEvent): Boolean {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    startY = params.y
                    dragging = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downX
                    val dy = event.rawY - downY
                    if (!dragging && dx < -slop * 2 && abs(dx) > abs(dy)) {
                        dragging = true
                        openPanel()
                    } else if (dragging || abs(dy) > slop) {
                        if (!dragging) dragging = true
                        params.y = (startY + dy).roundToInt().coerceIn(0, screenHeight() - view.height)
                        windows.updateViewLayout(view, params)
                    }
                }
                MotionEvent.ACTION_UP -> {
                    if (dragging) {
                        settings.edgeTabPosition = params.y.toFloat() / screenHeight()
                    } else {
                        view.performClick()
                    }
                }
            }
            return true
        }
    }

    // --- panel -----------------------------------------------------------------------------

    private fun openPanel() {
        showTab()
        if (panelWindow?.isAttachedToWindow == true) return
        val container = panelWindow ?: createPanelWindow().also { panelWindow = it }
        val metrics = resources.displayMetrics
        val params = WindowManager.LayoutParams(
            min(metrics.widthPixels, (PANEL_MAX_WIDTH_DP * metrics.density).roundToInt()),
            (screenHeight() * PANEL_HEIGHT).roundToInt(),
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.BOTTOM or Gravity.END
            @Suppress("DEPRECATION")
            softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
            windowAnimations = android.R.style.Animation_InputMethod
        }
        windows.addView(container, params)
        tab?.visibility = View.GONE
    }

    private fun createPanelWindow(): FrameLayout {
        val view = PanelView(this, this).apply {
            setBackgroundResource(R.drawable.panel_background)
            clipToOutline = true
        }
        panel = view
        return object : FrameLayout(this) {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean {
                if (event.keyCode == KeyEvent.KEYCODE_BACK && event.action == KeyEvent.ACTION_UP) {
                    closePanel()
                    return true
                }
                return super.dispatchKeyEvent(event)
            }
        }.apply {
            addView(view, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        }
    }

    override fun closePanel() {
        panelWindow?.takeIf { it.isAttachedToWindow }?.let { windows.removeView(it) }
        tab?.visibility = View.VISIBLE
    }

    override fun insertText(text: String) {
        closePanel()
        TextInsert.insert(this, text)
    }

    override fun launch(intent: Intent) {
        startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    override val screenCapture: (() -> Unit) = { requestScreen() }

    // --- zawartość ekranu ------------------------------------------------------------------

    private fun requestScreen() {
        val accessibility = NexusAccessibilityService.instance
        if (settings.screenCapture) {
            closePanel()
            tab?.visibility = View.GONE
            startActivity(ScreenCaptureActivity.intent(this))
            return
        }
        if (accessibility != null) {
            closePanel()
            // Chwila na powrót aplikacji pod panelem na pierwszy plan.
            tab?.postDelayed({ sendScreen(null) }, 350)
            return
        }
        Toast.makeText(this, "Włącz zrzut ekranu lub odczyt tekstu w ustawieniach Nexusa.", Toast.LENGTH_LONG).show()
        startActivity(Intent(this, SettingsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        closePanel()
    }

    private fun capture(code: Int, data: Intent) {
        try {
            ServiceCompat.startForeground(
                this,
                Notifications.ID_OVERLAY,
                notification(),
                overlayType() or ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION,
            )
            val projection = getSystemService(MediaProjectionManager::class.java).getMediaProjection(code, data)
            if (projection == null) {
                openPanel()
                return
            }
            ScreenCapture(projection, realMetrics()).capture { bitmap ->
                ServiceCompat.startForeground(this, Notifications.ID_OVERLAY, notification(), overlayType())
                sendScreen(bitmap?.let { ScreenContent.dataUrl(it).also { _ -> it.recycle() } })
            }
        } catch (error: Exception) {
            Log.w(TAG, "Zrzut ekranu nie powiódł się", error)
            Toast.makeText(this, "Nie udało się wykonać zrzutu ekranu.", Toast.LENGTH_LONG).show()
            openPanel()
        }
    }

    private fun sendScreen(image: String?) {
        val screen = NexusAccessibilityService.instance?.readScreen()
        val title = ScreenContent.appLabel(this, screen?.first)
        openPanel()
        if (image == null && screen?.second.isNullOrBlank()) {
            Toast.makeText(this, "Nie udało się odczytać ekranu.", Toast.LENGTH_SHORT).show()
            return
        }
        panel?.sendContext(PanelContext("screen", title, "", screen?.second.orEmpty(), image))
    }

    // --- pomocnicze ------------------------------------------------------------------------

    /** Typ usługi języczka: specialUse istnieje od Androida 14 (wcześniej bez typu). */
    private fun overlayType(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0

    private fun screenHeight(): Int = resources.displayMetrics.heightPixels

    private fun realMetrics(): DisplayMetrics {
        val metrics = DisplayMetrics().apply { setTo(resources.displayMetrics) }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val bounds = windows.maximumWindowMetrics.bounds
            metrics.widthPixels = bounds.width()
            metrics.heightPixels = bounds.height()
        } else {
            @Suppress("DEPRECATION")
            windows.defaultDisplay.getRealMetrics(metrics)
        }
        return metrics
    }

    private fun notification(): Notification {
        val settingsIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, SettingsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, Notifications.CHANNEL_OVERLAY)
            .setSmallIcon(R.drawable.ic_stat_nexus)
            .setContentTitle("Języczek Nexusa jest aktywny")
            .setContentText("Dotknij, aby zmienić ustawienia.")
            .setContentIntent(settingsIntent)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .build()
    }

    override fun onDestroy() {
        tab?.let { runCatching { windows.removeView(it) } }
        panelWindow?.takeIf { it.isAttachedToWindow }?.let { runCatching { windows.removeView(it) } }
        panel?.destroy()
        tab = null
        panel = null
        panelWindow = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "NexusJezyczek"
        private const val ACTION_SHOW_PANEL = "pl.danaco.nexus.jezyczek.PANEL"
        private const val ACTION_CAPTURE = "pl.danaco.nexus.jezyczek.ZRZUT"
        private const val EXTRA_CODE = "kod"
        private const val EXTRA_DATA = "dane"
        private const val TAB_WIDTH_DP = 14
        private const val TAB_HEIGHT_DP = 76
        private const val PANEL_MAX_WIDTH_DP = 520
        private const val PANEL_HEIGHT = 0.72f

        fun startIfEnabled(context: Context) {
            if (!AppSettings(context).edgeTab || !Settings.canDrawOverlays(context)) return
            try {
                context.startForegroundService(Intent(context, EdgeTabService::class.java))
            } catch (error: Exception) {
                Log.w(TAG, "Nie można uruchomić języczka", error)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, EdgeTabService::class.java))
        }

        fun showPanel(context: Context) {
            if (!AppSettings(context).edgeTab) return
            context.startForegroundService(Intent(context, EdgeTabService::class.java).setAction(ACTION_SHOW_PANEL))
        }

        /** Wynik zgody na zrzut ekranu (z [ScreenCaptureActivity]). */
        fun deliverCapture(context: Context, resultCode: Int, data: Intent) {
            context.startForegroundService(
                Intent(context, EdgeTabService::class.java)
                    .setAction(ACTION_CAPTURE)
                    .putExtra(EXTRA_CODE, resultCode)
                    .putExtra(EXTRA_DATA, data),
            )
        }

        private fun Intent.parcelableIntent(name: String): Intent? =
            if (Build.VERSION.SDK_INT >= 33) {
                getParcelableExtra(name, Intent::class.java)
            } else {
                @Suppress("DEPRECATION")
                getParcelableExtra(name)
            }
    }
}
