package pl.danaco.nexus.sms

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.text.format.DateUtils
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import pl.danaco.nexus.Nexus
import pl.danaco.nexus.R
import pl.danaco.nexus.access.TextInsert
import pl.danaco.nexus.config.AppSettings
import pl.danaco.nexus.config.DeviceKeyStore

/**
 * Szkice odpowiedzi na SMS: lista ostatnich wątków (odczyt na żądanie), szkic od Nexusa,
 * „Wstaw” (usługa dostępności), „Kopiuj”, „Otwórz w Wiadomościach”. Nexus nigdy nie wysyła SMS-ów.
 */
class SmsActivity : AppCompatActivity() {
    private lateinit var threadsView: ListView
    private lateinit var detail: View
    private lateinit var reply: EditText
    private lateinit var status: TextView
    private lateinit var draftButton: Button
    private var threads: List<SmsThread> = emptyList()
    private var current: SmsThread? = null
    private var draftJob: Job? = null

    private val permission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) load() else Toast.makeText(this, "Bez zgody Nexus nie odczyta wiadomości.", Toast.LENGTH_LONG).show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_sms)
        threadsView = findViewById(R.id.sms_threads)
        detail = findViewById(R.id.sms_detail)
        reply = findViewById(R.id.sms_reply)
        status = findViewById(R.id.sms_status)
        draftButton = findViewById(R.id.sms_draft)
        findViewById<View>(R.id.sms_back).setOnClickListener { onBackPressedDispatcher.onBackPressed() }
        findViewById<View>(R.id.sms_refresh).setOnClickListener { load() }
        findViewById<View>(R.id.sms_grant).setOnClickListener { permission.launch(Manifest.permission.READ_SMS) }
        draftButton.setOnClickListener { draft() }
        findViewById<View>(R.id.sms_copy).setOnClickListener { replyText()?.let { TextInsert.copy(this, it) } }
        findViewById<View>(R.id.sms_insert).setOnClickListener { insert() }
        findViewById<View>(R.id.sms_open).setOnClickListener { openMessages() }
        threadsView.setOnItemClickListener { _, _, position, _ -> showThread(threads[position]) }
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (current != null) showList() else finish()
                }
            },
        )
    }

    override fun onResume() {
        super.onResume()
        if (!AppSettings(this).sms) {
            Toast.makeText(this, "Moduł SMS jest wyłączony w ustawieniach Nexusa.", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        if (current == null) load()
    }

    private fun hasPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED

    private fun load() {
        val consent = findViewById<View>(R.id.sms_consent)
        if (!hasPermission()) {
            consent.visibility = View.VISIBLE
            threadsView.visibility = View.GONE
            return
        }
        consent.visibility = View.GONE
        lifecycleScope.launch {
            threads = withContext(Dispatchers.IO) { SmsThreads.group(SmsReader.recent(this@SmsActivity)) }.take(50)
            threadsView.adapter = ThreadAdapter(threads)
            findViewById<View>(R.id.sms_empty).visibility = if (threads.isEmpty()) View.VISIBLE else View.GONE
            if (current == null) showList()
        }
    }

    private fun showList() {
        draftJob?.cancel()
        current = null
        detail.visibility = View.GONE
        threadsView.visibility = View.VISIBLE
        findViewById<TextView>(R.id.sms_title).setText(R.string.sms_title)
    }

    private fun showThread(thread: SmsThread) {
        current = thread
        threadsView.visibility = View.GONE
        findViewById<View>(R.id.sms_empty).visibility = View.GONE
        detail.visibility = View.VISIBLE
        findViewById<TextView>(R.id.sms_title).text = thread.address
        findViewById<TextView>(R.id.sms_conversation).text = thread.messages.reversed().joinToString("\n\n") { message ->
            val who = if (message.incoming) thread.address else "Ja"
            "$who · ${DateUtils.getRelativeTimeSpanString(message.date)}\n${message.body}"
        }
        reply.setText("")
        status.visibility = View.GONE
    }

    private fun draft() {
        val thread = current ?: return
        if (!DeviceKeyStore.get(this).hasKey) {
            showStatus("Najpierw otwórz Nexusa i zaloguj się – aplikacja połączy się automatycznie.")
            return
        }
        val hint = findViewById<EditText>(R.id.sms_hint).text.toString()
        draftJob?.cancel()
        draftButton.isEnabled = false
        reply.setText("")
        showStatus("Nexus przygotowuje szkic…")
        draftJob = lifecycleScope.launch {
            val api = Nexus.api(this@SmsActivity)
            val text = StringBuilder()
            try {
                val conversation = api.createConversation("SMS: ${thread.address}".take(200))
                val run = api.sendMessage(conversation, SmsPrompt.build(thread, hint))
                var failed = ""
                api.runEvents(run).collect { event ->
                    when (event.type) {
                        "text.delta" -> {
                            text.append(event.text)
                            reply.setText(text)
                        }
                        "text.block" -> text.clear()
                        "run.failed", "run.cancelled" -> failed = event.data.optString("error", "Zadanie nie powiodło się.")
                    }
                }
                reply.setText(SmsPrompt.clean(text.toString()))
                reply.setSelection(reply.text.length)
                if (failed.isNotBlank()) showStatus(failed) else showStatus("Szkic gotowy – przejrzyj go przed wysłaniem.")
            } catch (error: Exception) {
                if (error is kotlinx.coroutines.CancellationException) throw error
                Nexus.handleFailure(this@SmsActivity, error)
                showStatus(Nexus.describe(error))
            } finally {
                draftButton.isEnabled = true
            }
        }
    }

    private fun showStatus(text: String) {
        status.text = text
        status.visibility = View.VISIBLE
    }

    private fun replyText(): String? = reply.text.toString().trim().ifEmpty {
        Toast.makeText(this, "Szkic jest pusty.", Toast.LENGTH_SHORT).show()
        null
    }

    private fun insert() {
        val text = replyText() ?: return
        // Okno Nexusa znika, fokus wraca do pola aplikacji, z której otwarto panel.
        finish()
        TextInsert.insert(applicationContext, text)
    }

    private fun openMessages() {
        val thread = current ?: return
        val text = reply.text.toString().trim()
        val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(thread.address)))
            .putExtra("sms_body", text)
        try {
            startActivity(intent)
        } catch (_: Exception) {
            Toast.makeText(this, "Brak aplikacji do wiadomości.", Toast.LENGTH_LONG).show()
        }
    }

    private inner class ThreadAdapter(private val items: List<SmsThread>) : BaseAdapter() {
        override fun getCount() = items.size

        override fun getItem(position: Int) = items[position]

        override fun getItemId(position: Int) = items[position].threadId

        override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
            val view = convertView ?: layoutInflater.inflate(R.layout.item_sms_thread, parent, false)
            val thread = items[position]
            view.findViewById<TextView>(R.id.thread_address).text = thread.address
            view.findViewById<TextView>(R.id.thread_time).text = DateUtils.getRelativeTimeSpanString(thread.latest.date)
            view.findViewById<TextView>(R.id.thread_body).text =
                if (thread.latest.incoming) thread.latest.body else getString(R.string.sms_own_message, thread.latest.body)
            return view
        }
    }
}
