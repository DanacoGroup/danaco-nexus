// Pusta strona to najgorsza możliwa awaria interfejsu: użytkownik nie wie, czy stracił
// pracę, ani co zrobić. Granica zamienia ją na zdanie i przycisk.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GranicaBledu } from "../ui/GranicaBledu";

function Wybuchowy(): never {
  throw new Error("celowy błąd w rysowaniu");
}

let konsola: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  // React wypisuje złapany wyjątek do konsoli — w teście to szum, nie sygnał.
  konsola = vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  konsola.mockRestore();
  cleanup();
});

describe("granica błędu", () => {
  it("przepuszcza treść, gdy nic się nie dzieje", () => {
    render(
      <GranicaBledu>
        <p>zawartość okna</p>
      </GranicaBledu>,
    );

    expect(screen.getByText("zawartość okna")).toBeTruthy();
  });

  it("zamiast pustej strony pokazuje wyjaśnienie i wyjście", () => {
    render(
      <GranicaBledu>
        <Wybuchowy />
      </GranicaBledu>,
    );

    expect(screen.getByText(/Coś się tu zacięło/)).toBeTruthy();
    expect(screen.getByText(/Twoje rozmowy i pliki są na serwerze/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Odśwież okno/ })).toBeTruthy();
  });
});
