// Logotyp pobiera tylko ten plik, który widać.
//
// Wcześniej w drzewie stały oba warianty, a jeden był chowany klasą `dark:hidden`.
// Przeglądarka pobiera obrazek także przy `display: none`, więc każde wejście ciągnęło
// 9 kB grafiki, której nikt nie zobaczy — w pasku i w stopce portalu razem 18 kB.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Logotype } from "../components/icons";

afterEach(() => {
  cleanup();
  document.documentElement.classList.remove("dark");
});

describe("logotyp", () => {
  it("wstawia jeden obrazek w wariancie zgodnym z motywem", () => {
    document.documentElement.classList.add("dark");
    render(<Logotype />);
    const obrazki = screen.getAllByAltText("Danaco Nexus");
    expect(obrazki).toHaveLength(1);
    expect(obrazki[0]?.getAttribute("src")).toBe("/znak/logo-poziome-ciemny.svg");
  });

  it("w motywie jasnym bierze wariant jasny", () => {
    render(<Logotype />);
    expect(screen.getByAltText("Danaco Nexus").getAttribute("src")).toBe("/znak/logo-poziome-jasny.svg");
  });

  it("zmienia wariant, gdy zmieni się motyw okna", async () => {
    render(<Logotype />);
    document.documentElement.classList.add("dark");
    await waitFor(() =>
      expect(screen.getByAltText("Danaco Nexus").getAttribute("src")).toBe("/znak/logo-poziome-ciemny.svg"),
    );
  });
});
