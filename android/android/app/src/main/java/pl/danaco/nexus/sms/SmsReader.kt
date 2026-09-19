package pl.danaco.nexus.sms

import android.content.Context
import android.provider.Telephony

/** Odczyt ostatnich SMS-ów (READ_SMS) – tylko na żądanie, nic nie jest zapisywane ani wysyłane. */
object SmsReader {
    fun recent(context: Context, limit: Int = 300): List<SmsMessage> {
        val columns = arrayOf(
            Telephony.Sms.THREAD_ID,
            Telephony.Sms.ADDRESS,
            Telephony.Sms.BODY,
            Telephony.Sms.DATE,
            Telephony.Sms.TYPE,
        )
        val result = mutableListOf<SmsMessage>()
        context.contentResolver.query(
            Telephony.Sms.CONTENT_URI,
            columns,
            null,
            null,
            "${Telephony.Sms.DATE} DESC",
        )?.use { cursor ->
            while (cursor.moveToNext() && result.size < limit) {
                val type = cursor.getInt(4)
                if (type != Telephony.Sms.MESSAGE_TYPE_INBOX && type != Telephony.Sms.MESSAGE_TYPE_SENT) continue
                result += SmsMessage(
                    threadId = cursor.getLong(0),
                    address = cursor.getString(1).orEmpty(),
                    body = cursor.getString(2).orEmpty(),
                    date = cursor.getLong(3),
                    incoming = type == Telephony.Sms.MESSAGE_TYPE_INBOX,
                )
            }
        }
        return result
    }
}
