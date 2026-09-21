package pl.danaco.nexus.sms

import android.content.Context
import android.provider.Telephony

/** Odczyt ostatnich SMS-ów (READ_SMS) – tylko na żądanie użytkownika, bez zapisu na urządzeniu.
 *
 * **Sam odczyt niczego nie wysyła**, ale funkcja, która z niego korzysta, owszem: ekran
 * „Szkice odpowiedzi na SMS” (`SmsActivity`) zakłada rozmowę na serwerze i przekazuje do
 * niej treść wątku (`api.sendMessage(..., SmsPrompt.build(thread, hint))`), żeby model
 * napisał szkic. Wcześniejszy komentarz mówił „nic nie jest zapisywane ani wysyłane” —
 * to prawda o tym pliku, ale nieprawda o funkcji jako całości, a taki komentarz jest
 * groźniejszy od braku komentarza, bo usypia przy przeglądzie prywatności.
 *
 * Treść SMS-ów to dane osobowe **także osób trzecich** (nadawców), więc ta czynność musi
 * być opisana w rejestrze czynności przetwarzania i w polityce prywatności. */
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
