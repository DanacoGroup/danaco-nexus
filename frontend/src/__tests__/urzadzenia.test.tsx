// Moduł Sprzęt: teksty o kluczach urządzeń mają mówić to, co naprawdę robi serwer i aplikacje.
// Cofnięcie klucza założonego przez okno aplikacji wylogowuje to okno; klucz z formularza
// jest dla innego urządzenia i nie wiąże sesji przeglądarki, która go wydała.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Device } from "../shell/startApi";

const devices = vi.fn();
const createDevice = vi.fn();
const revokeDevice = vi.fn();

vi.mock("../shell/startApi", async (oryginal) => {
  const rzeczywisty = await oryginal<typeof import("../shell/startApi")>();
  return {
    ...rzeczywisty,
    fetchDownloads: () => Promise.resolve([]),
    startApi: { ...rzeczywisty.startApi, devices, createDevice, revokeDevice },
  };
});

vi.mock("../shell/push", () => ({
  pushStatus: () => Promise.resolve("unsupported"),
  enablePush: vi.fn(),
  disablePush: vi.fn(),
}));

const { DevicesPage, KIND_HINTS } = await import("../modules/urzadzenia/DevicesPage");
const { startApi: prawdziweApi } = await vi.importActual<typeof import("../shell/startApi")>("../shell/startApi");

const klucz = (id: string, name: string, wylogowuje_okno: boolean): Device => ({
  id,
  name,
  kind: "android",
  created_at: "2026-09-20T10:00:00Z",
  last_used_at: null,
  revoked: false,
  wylogowuje_okno,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  devices.mockReset();
  createDevice.mockReset();
  revokeDevice.mockReset();
});

describe("klucze urządzeń", () => {
  it("podpowiedź dla telefonu nie każe wpisywać klucza, którego aplikacja nie przyjmuje", () => {
    expect(KIND_HINTS.android).not.toMatch(/ręcznie|wpisz|wklej/);
    expect(KIND_HINTS.android).toContain("powstanie sam");
  });

  it("formularz zakłada klucz dla innego urządzenia, bez wiązania sesji przeglądarki", async () => {
    const zapytanie = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ token: "nxd_x" }), { status: 201 }));
    await prawdziweApi.createDevice("Chrome – biuro", "rozszerzenie");
    const tresc = JSON.parse(String(zapytanie.mock.calls[0][1]?.body));
    expect(tresc).toEqual({ name: "Chrome – biuro", kind: "rozszerzenie", dla_innego_urzadzenia: true });
  });

  it("po utworzeniu klucza nie obiecuje, że „Cofnij” wyloguje tamto urządzenie", async () => {
    devices.mockResolvedValue([]);
    createDevice.mockResolvedValue({ ...klucz("1", "Chrome – biuro", false), kind: "rozszerzenie", token: "nxd_abc" });
    render(<DevicesPage />);
    fireEvent.click(screen.getByRole("button", { name: /Utwórz klucz/ }));
    const uwaga = await screen.findByText(/nie wysyłaj go nikomu/);
    expect(uwaga.textContent).toContain("nie kończy");
    expect(uwaga.textContent).not.toContain("Zgubione urządzenie odłącz");
  });

  it("przy cofaniu mówi, czy okno aplikacji zostanie wylogowane", async () => {
    devices.mockResolvedValue([klucz("1", "Telefon", true), klucz("2", "Stary telefon", false)]);
    revokeDevice.mockResolvedValue({ ok: true });
    const pytanie = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<DevicesPage />);

    await screen.findByText("Telefon");
    expect(screen.getByText("Telefon").closest("li")?.textContent).toContain("wyloguje też okno aplikacji");
    expect(screen.getByText("Stary telefon").closest("li")?.textContent).not.toContain("wyloguje");
    const [cofnijTelefon, cofnijStary] = screen.getAllByRole("button", { name: /Cofnij/ });

    fireEvent.click(cofnijTelefon);
    expect(pytanie).toHaveBeenLastCalledWith(expect.stringContaining("zostanie wylogowane"));
    fireEvent.click(cofnijStary);
    expect(pytanie).toHaveBeenLastCalledWith(expect.stringContaining("Klucz przestanie działać od razu."));
    await waitFor(() => expect(revokeDevice).not.toHaveBeenCalled());
  });
});
