// Domknięcie logowania: znak w ruchu, nie makieta produktu.
//
// Pakiet ruchu wydał na logowanie ujęcie `logowanie-ciemny`/`logowanie-jasny`, ale to
// makieta: cudzy formularz z wpisanym adresem i powitanie „Dzień dobry, Dariuszu”.
// Test pilnuje, że wejście do aplikacji i wejście na konto próbne rysują znak.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { EkranPrzejscia } from "../EkranPrzejscia";

afterEach(cleanup);

describe("ekran przejścia", () => {
  it("przy podanym momencie rysuje znak, a nie nagranie", () => {
    const { container } = render(<EkranPrzejscia moment="logowanie" etykieta="Logowanie" onKoniec={() => undefined} />);
    expect(container.querySelector(".znak-ruch")?.getAttribute("data-moment")).toBe("logowanie");
    expect(container.querySelector("video")).toBeNull();
  });

  it("bez momentu zostaje przy nagraniu z pakietu", () => {
    const { container } = render(
      <EkranPrzejscia nazwa="moment-wylogowanie" etykieta="Wylogowywanie" onKoniec={() => undefined} />,
    );
    expect(container.querySelector("video")).not.toBeNull();
    expect(container.querySelector(".znak-ruch")).toBeNull();
  });

  it("przepuszcza dalej także wtedy, gdy nic się nie odtworzy", () => {
    vi.useFakeTimers();
    const koniec = vi.fn();
    render(<EkranPrzejscia moment="logowanie" etykieta="Logowanie" onKoniec={koniec} bezpiecznikMs={900} />);
    expect(koniec).not.toHaveBeenCalled();
    vi.advanceTimersByTime(900);
    expect(koniec).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});
