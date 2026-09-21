// Menu konta w panelu bocznym: jedno wejście do wszystkiego, co dotyczy „mnie”.
//
// Wcześniej przy nazwie użytkownika stały dwie ikony bez nazwy i nic poza nimi:
// ustawienia, wygląd i rozliczenia leżały rozsypane po modułach, a stanu dostępu nie dało
// się sprawdzić bez wyjścia z rozmowy.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Sidebar } from "../components/Sidebar";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function panel(nadpisz: Partial<Parameters<typeof Sidebar>[0]> = {}) {
  const props = {
    conversations: [],
    currentId: null,
    username: "Anna Kowalska",
    cloudUrl: "",
    open: true,
    theme: "dark" as const,
    onTheme: () => undefined,
    onSelect: () => undefined,
    onNew: () => undefined,
    onRename: () => undefined,
    onDelete: () => undefined,
    onLogout: () => undefined,
    onZwin: () => undefined,
    zwiniety: false,
    onClose: () => undefined,
    ...nadpisz,
  };
  return render(<Sidebar {...props} />);
}

describe("menu konta", () => {
  it("jest zwinięte, dopóki nikt go nie otworzy", () => {
    panel();
    const przycisk = screen.getByRole("button", { name: /Anna Kowalska/ });
    expect(przycisk.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("menuitem", { name: /Wyloguj/ })).toBeNull();
  });

  it("po otwarciu prowadzi do ustawień, planu i wylogowania", () => {
    let ustawienia = 0;
    let dostep = 0;
    panel({ onUstawienia: () => (ustawienia += 1), onDostep: () => (dostep += 1) });
    fireEvent.click(screen.getByRole("button", { name: /Anna Kowalska/ }));
    expect(screen.getByRole("menuitem", { name: /Ustawienia/ })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: /Plan i dostęp/ })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: /Wyloguj/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: /Plan i dostęp/ }));
    expect(dostep).toBe(1);
    expect(ustawienia).toBe(0);
  });

  it("pokazuje nazwę ustawionego motywu, a nie samą ikonę", () => {
    panel({ theme: "light" });
    fireEvent.click(screen.getByRole("button", { name: /Anna Kowalska/ }));
    expect(screen.getByRole("menuitem", { name: /Motyw jasny/ })).toBeTruthy();
  });

  it("nie pokazuje pozycji, których powłoka nie obsługuje", () => {
    panel();
    fireEvent.click(screen.getByRole("button", { name: /Anna Kowalska/ }));
    expect(screen.queryByRole("menuitem", { name: /Ustawienia/ })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: /Plan i dostęp/ })).toBeNull();
    expect(screen.getByRole("menuitem", { name: /Wyloguj/ })).toBeTruthy();
  });
});
