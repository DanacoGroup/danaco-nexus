package pl.danaco.nexus.overlay

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/** Systemowa zgoda na zrzut ekranu (MediaProjection) – pytana przy każdym zrzucie z języczka. */
class ScreenCaptureActivity : ComponentActivity() {
    private val consent = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode == Activity.RESULT_OK && data != null) {
            EdgeTabService.deliverCapture(this, result.resultCode, data)
        } else {
            EdgeTabService.showPanel(this)
        }
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null) {
            val manager = getSystemService(MediaProjectionManager::class.java)
            consent.launch(manager.createScreenCaptureIntent())
        }
    }

    companion object {
        fun intent(context: Context): Intent =
            Intent(context, ScreenCaptureActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
    }
}
