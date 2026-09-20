// Pasmo treści: jedna szerokość dla całej części publicznej (strona produktu i portal).
//
// Topbar, hero, każda sekcja, treść portalu i stopka mają zaczynać się w tej samej
// pionowej linii. Wcześniej strona produktu i portal miały osobne szerokości
// (`max-w-(--container-page)` kontra `max-w-6xl`), więc przejście z jednej na drugą
// przesuwało całą treść w bok. Margines rośnie ze szerokością okna, żeby na laptopie
// treść nie kleiła się do krawędzi.

export const PASMO = "mx-auto w-full max-w-(--container-page) px-5 sm:px-8 xl:px-10";
