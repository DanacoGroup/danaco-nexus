package pl.danaco.nexus.voice

import org.junit.Assert.assertEquals
import org.junit.Test

/** Te same przypadki co frontend/src/__tests__/sentences.test.ts – zachowanie musi być identyczne. */
class SentencesTest {
    @Test
    fun `zwraca pelne zdania i zostawia niedokonczona reszte`() {
        val text = "Sprawdziłem fakturę numer siedem. Kwota brutto wynosi tysiąc osiemset. Termin"
        val result = Sentences.take(text, 0, false)
        assertEquals(listOf("Sprawdziłem fakturę numer siedem.", "Kwota brutto wynosi tysiąc osiemset."), result.chunks)
        assertEquals("Termin", text.substring(result.next).trim())
    }

    @Test
    fun `laczy krotkie zdania i oddaje reszte na koncu`() {
        val text = "Dobrze. Już. Zrobione w całości, plik jest gotowy"
        assertEquals(emptyList<String>(), Sentences.take(text, 0, false).chunks)
        assertEquals(listOf("Dobrze. Już. Zrobione w całości, plik jest gotowy"), Sentences.take(text, 0, true).chunks)
    }

    @Test
    fun `kontynuuje od poprzedniej pozycji`() {
        val text = "Pierwsze zdanie jest dość długie. Drugie zdanie też jest dość długie."
        val first = Sentences.take(text, 0, false)
        assertEquals(listOf("Pierwsze zdanie jest dość długie.", "Drugie zdanie też jest dość długie."), first.chunks)
        assertEquals(emptyList<String>(), Sentences.take(text, first.next, true).chunks)
    }

    @Test
    fun `nie dzieli liczb z kropka`() {
        val text = "Kwota wynosi 1 845.00 zł brutto za całość usługi."
        assertEquals(listOf("Kwota wynosi 1 845.00 zł brutto za całość usługi."), Sentences.take(text, 0, false).chunks)
    }

    @Test
    fun `usuwa markdown i kod`() {
        val spoken = Sentences.speakable("**Kwota:** 10 zł ```kod``` [link](http://x)").replace(Regex("\\s+"), " ").trim()
        assertEquals("Kwota: 10 zł link", spoken)
    }

    @Test
    fun `zaczyna czytac od pierwszego przecinka dlugiego zdania`() {
        val text = "Jesienią pogoda bywa kapryśna i zmienna, chłodne ranki przechodzą w słoneczne popołudnia"
        val result = Sentences.take(text, 0, false)
        assertEquals(listOf("Jesienią pogoda bywa kapryśna i zmienna,"), result.chunks)
        assertEquals("chłodne ranki przechodzą w słoneczne popołudnia", text.substring(result.next).trim())
    }

    @Test
    fun `woli pelne zdanie gdy konczy sie przed przecinkiem`() {
        val text = "To jest pełne, krótkie zdanie testowe. Dalej, coś jeszcze"
        assertEquals(listOf("To jest pełne, krótkie zdanie testowe."), Sentences.take(text, 0, false).chunks)
    }

    @Test
    fun `krotki tekst bez granic nie jest dzielony`() {
        assertEquals(emptyList<String>(), Sentences.take("Tak", 0, false).chunks)
        assertEquals(listOf("Tak"), Sentences.take("Tak", 0, true).chunks)
    }

    @Test
    fun `odpowiedz strumieniowana w kawalkach`() {
        val reply = ReplySpeech()
        val out = mutableListOf<String>()
        out += reply.onDelta("Sprawdziłem fakturę numer ")
        out += reply.onDelta("siedem. Kwota brutto wynosi ")
        out += reply.onDelta("tysiąc osiemset. Termin")
        reply.onBlock()
        out += reply.onDelta("płatności mija jutro")
        out += reply.finish()
        assertEquals(
            listOf("Sprawdziłem fakturę numer siedem.", "Kwota brutto wynosi tysiąc osiemset.", "Termin\n\npłatności mija jutro"),
            out,
        )
    }
}
