package pl.danaco.nexus.voice

import java.io.ByteArrayOutputStream

/** Zapis nagrania 16-bitowego PCM jako WAV (format przyjmowany przez /api/voice/transcribe). */
object Wav {
    fun encode(pcm: ShortArray, count: Int = pcm.size, sampleRate: Int = 16_000, channels: Int = 1): ByteArray {
        val dataBytes = count * 2
        val out = ByteArrayOutputStream(44 + dataBytes)
        fun int32(value: Int) {
            out.write(value and 0xff)
            out.write(value shr 8 and 0xff)
            out.write(value shr 16 and 0xff)
            out.write(value shr 24 and 0xff)
        }
        fun int16(value: Int) {
            out.write(value and 0xff)
            out.write(value shr 8 and 0xff)
        }
        out.write("RIFF".toByteArray(Charsets.US_ASCII))
        int32(36 + dataBytes)
        out.write("WAVE".toByteArray(Charsets.US_ASCII))
        out.write("fmt ".toByteArray(Charsets.US_ASCII))
        int32(16)
        int16(1)
        int16(channels)
        int32(sampleRate)
        int32(sampleRate * channels * 2)
        int16(channels * 2)
        int16(16)
        out.write("data".toByteArray(Charsets.US_ASCII))
        int32(dataBytes)
        val buffer = ByteArray(dataBytes)
        for (index in 0 until count) {
            val sample = pcm[index].toInt()
            buffer[index * 2] = (sample and 0xff).toByte()
            buffer[index * 2 + 1] = (sample shr 8 and 0xff).toByte()
        }
        out.write(buffer)
        return out.toByteArray()
    }
}
