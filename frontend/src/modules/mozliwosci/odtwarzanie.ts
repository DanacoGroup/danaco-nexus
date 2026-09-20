// Bezpieczne uruchomienie nagrania.
//
// `HTMLMediaElement.play()` zwraca obietnicę dopiero od pewnych wersji przeglądarek,
// a w środowisku testowym (jsdom) nie zwraca nic. Wywołanie `.catch` wprost kończy się
// wtedy wyjątkiem, więc opakowujemy wynik.

export function odtworz(element: HTMLMediaElement): void {
  void Promise.resolve(element.play()).catch(() => undefined);
}
