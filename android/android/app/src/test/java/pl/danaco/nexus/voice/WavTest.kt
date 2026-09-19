package pl.danaco.nexus.voice

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class WavTest {
    @Test
    fun `naglowek wav i probki little endian`() {
        val pcm = shortArrayOf(0, 1, -1, Short.MAX_VALUE, Short.MIN_VALUE)
        val wav = Wav.encode(pcm, sampleRate = 16_000)
        assertEquals(44 + pcm.size * 2, wav.size)
        assertEquals("RIFF", String(wav, 0, 4, Charsets.US_ASCII))
        assertEquals("WAVE", String(wav, 8, 4, Charsets.US_ASCII))
        assertEquals("data", String(wav, 36, 4, Charsets.US_ASCII))
        val header = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(36 + pcm.size * 2, header.getInt(4))
        assertEquals(1, header.getShort(20).toInt())
        assertEquals(1, header.getShort(22).toInt())
        assertEquals(16_000, header.getInt(24))
        assertEquals(32_000, header.getInt(28))
        assertEquals(16, header.getShort(34).toInt())
        assertEquals(pcm.size * 2, header.getInt(40))
        val samples = ShortArray(pcm.size) { header.getShort(44 + it * 2) }
        assertArrayEquals(pcm, samples)
    }

    @Test
    fun `laczenie ramek mikrofonu`() {
        val joined = MicRecorder.concat(listOf(shortArrayOf(1, 2), shortArrayOf(), shortArrayOf(3)))
        assertArrayEquals(shortArrayOf(1, 2, 3), joined)
        assertEquals(640, MicRecorder.FRAME_SAMPLES)
    }
}
