import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentStatus, czasZegara, type AgentRun } from "../AgentStatus";
import { Badge, Tag } from "../Badge";
import { BeforeAfterCompare } from "../BeforeAfterCompare";
import { Button, IconButton } from "../Button";
import { Checkbox } from "../Checkbox";
import { CommandPalette, type CommandItem } from "../CommandPalette";
import { Dialog } from "../Dialog";
import { EmptyState } from "../EmptyState";
import { Field } from "../Field";
import { CheckIcon } from "../Icons";
import { Input } from "../Input";
import { Menu } from "../Menu";
import { Progress, ProgressRing, Spinner } from "../Progress";
import { Select } from "../Select";
import { Sheet } from "../Sheet";
import { Skeleton } from "../Skeleton";
import { Stagger } from "../Stagger";
import { Switch } from "../Switch";
import { Table } from "../Table";
import { Tabs } from "../Tabs";
import { ToastProvider, useToast } from "../Toast";
import { Tooltip } from "../Tooltip";
import { ariaKeyshortcuts, cx, shortcutLabel } from "../types";

afterEach(cleanup);

describe("pomocniki", () => {
  it("skleja klasy i pomija puste", () => {
    expect(cx("a", false, undefined, "b")).toBe("a b");
  });

  it("zapisuje skrót w postaci ARIA", () => {
    expect(ariaKeyshortcuts(["Ctrl", "⏎"])).toBe("Control+Enter");
    expect(shortcutLabel(["Ctrl", "K"])).toContain("K");
  });

  it("liczy zegar agenta w mm:ss", () => {
    expect(czasZegara(74_000)).toBe("01:14");
    expect(czasZegara(-5)).toBe("00:00");
  });
});

describe("Button", () => {
  it("wywołuje działanie i ogłasza skrót", () => {
    const klik = vi.fn();
    render(
      <Button variant="primary" shortcut={["Ctrl", "⏎"]} onClick={klik}>
        Zapisz
      </Button>,
    );
    const przycisk = screen.getByRole("button", { name: /Zapisz/ });
    expect(przycisk.getAttribute("aria-keyshortcuts")).toBe("Control+Enter");
    fireEvent.click(przycisk);
    expect(klik).toHaveBeenCalledTimes(1);
  });

  it("w stanie ładowania jest zajęty i nie wywołuje działania", () => {
    const klik = vi.fn();
    render(
      <Button loading loadingLabel="Zapisuję" onClick={klik}>
        Zapisz
      </Button>,
    );
    const przycisk = screen.getByRole("button", { name: "Zapisuję" });
    expect(przycisk.getAttribute("aria-busy")).toBe("true");
    fireEvent.click(przycisk);
    expect(klik).not.toHaveBeenCalled();
  });

  it("wyłączony z powodem zostaje w kolejności tabulacji", () => {
    render(
      <Button disabled disabledReason="Poczekaj na przesłanie plików">
        Wyślij
      </Button>,
    );
    const przycisk = screen.getByRole("button", { name: "Wyślij" });
    expect(przycisk.getAttribute("aria-disabled")).toBe("true");
    expect(przycisk.hasAttribute("disabled")).toBe(false);
  });

  it("IconButton ma nazwę dostępną i stan wciśnięcia", () => {
    render(<IconButton icon={<CheckIcon />} label="Pokaż panel" pressed />);
    expect(screen.getByRole("button", { name: "Pokaż panel" }).getAttribute("aria-pressed")).toBe("true");
  });
});

describe("Tooltip", () => {
  it("pokazuje dymek przy fokusie i wiąże go z elementem", () => {
    render(
      <Tooltip content="Załącz plik" shortcut={["Ctrl", "U"]}>
        <button type="button">Załącz</button>
      </Tooltip>,
    );
    const przycisk = screen.getByRole("button", { name: "Załącz" });
    fireEvent.focusIn(przycisk);
    const dymek = screen.getByRole("tooltip");
    expect(dymek.textContent).toContain("Załącz plik");
    expect(przycisk.getAttribute("aria-describedby")).toBe(dymek.id);
  });
});

describe("pola formularzy", () => {
  it("Input wiąże etykietę, pomoc i błąd", () => {
    render(<Input label="Adres e-mail" value="jan" onChange={() => {}} description="Służbowy" error="Wpisz pełny adres." />);
    const pole = screen.getByLabelText("Adres e-mail");
    expect(pole.getAttribute("aria-invalid")).toBe("true");
    const opis = pole.getAttribute("aria-describedby") ?? "";
    expect(opis.split(" ")).toHaveLength(2);
    expect(screen.getByText("Wpisz pełny adres.")).toBeTruthy();
  });

  it("Input czyści wartość przyciskiem", () => {
    const zmiana = vi.fn();
    render(<Input label="Nazwa" value="umowa" onChange={zmiana} clearable />);
    fireEvent.click(screen.getByRole("button", { name: "Wyczyść: Nazwa" }));
    expect(zmiana).toHaveBeenCalledWith("");
  });

  it("Checkbox obsługuje stan mieszany", () => {
    const zmiana = vi.fn();
    render(<Checkbox checked="mixed" onChange={zmiana} ariaLabel="Zaznacz wszystkie" />);
    const pole = screen.getByRole("checkbox", { name: "Zaznacz wszystkie" });
    expect(pole.getAttribute("aria-checked")).toBe("mixed");
    fireEvent.click(pole);
    expect(zmiana).toHaveBeenCalledWith(true);
  });

  it("Switch przełącza i opisuje stan", () => {
    const zmiana = vi.fn();
    render(<Switch checked={false} onChange={zmiana} label="Indeksuj nowe pliki" description="Działa od razu" />);
    const przelacznik = screen.getByRole("switch", { name: "Indeksuj nowe pliki" });
    expect(przelacznik.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(przelacznik);
    expect(zmiana).toHaveBeenCalledWith(true);
  });

  it("Select otwiera listę i wybiera opcję z klawiatury", () => {
    const zmiana = vi.fn();
    render(
      <Select
        label="Język OCR"
        value={null}
        onChange={zmiana}
        options={[
          { value: "pol", label: "Polski" },
          { value: "eng", label: "Angielski" },
        ]}
      />,
    );
    const wyzwalacz = screen.getByRole("combobox", { name: "Język OCR" });
    fireEvent.keyDown(wyzwalacz, { key: "ArrowDown" });
    expect(wyzwalacz.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(wyzwalacz, { key: "ArrowDown" });
    fireEvent.keyDown(wyzwalacz, { key: "Enter" });
    expect(zmiana).toHaveBeenCalledWith("eng");
  });
});

describe("Menu", () => {
  it("otwiera menu i uruchamia pozycję strzałkami", () => {
    const usun = vi.fn();
    render(
      <Menu
        label="Działania rozmowy"
        trigger={<button type="button">Więcej</button>}
        items={[
          { id: "rename", label: "Zmień nazwę" },
          { type: "separator" },
          { id: "delete", label: "Usuń", destructive: true, onSelect: usun },
        ]}
      />,
    );
    const wyzwalacz = screen.getByRole("button", { name: "Więcej" });
    expect(wyzwalacz.getAttribute("aria-haspopup")).toBe("menu");
    fireEvent.click(wyzwalacz);
    const menu = screen.getByRole("menu", { name: "Działania rozmowy" });
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(2);
    fireEvent.keyDown(menu, { key: "ArrowDown" });
    fireEvent.keyDown(menu, { key: "Enter" });
    expect(usun).toHaveBeenCalledTimes(1);
  });
});

describe("Tabs", () => {
  it("przenosi wybór strzałką w trybie automatycznym", () => {
    const zmiana = vi.fn();
    render(
      <Tabs
        label="Typy plików"
        value="wszystkie"
        onChange={zmiana}
        items={[
          { value: "wszystkie", label: "Wszystkie" },
          { value: "dokumenty", label: "Dokumenty", count: 128 },
        ]}
      >
        <p>Treść</p>
      </Tabs>,
    );
    const zakladka = screen.getByRole("tab", { name: /Wszystkie/ });
    expect(zakladka.getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(zakladka, { key: "ArrowRight" });
    expect(zmiana).toHaveBeenCalledWith("dokumenty");
    expect(screen.getByRole("tabpanel").textContent).toContain("Treść");
  });
});

describe("Table", () => {
  const wiersze = [
    { id: "1", nazwa: "umowa.pdf", rozmiar: "2,4 MB" },
    { id: "2", nazwa: "aneks.docx", rozmiar: "1,1 MB" },
  ];

  it("sortuje, zaznacza i ogłasza kierunek", () => {
    const sortowanie = vi.fn();
    const zaznaczenie = vi.fn();
    render(
      <Table
        label="Pliki"
        rows={wiersze}
        rowId={(wiersz) => wiersz.id}
        sort={{ key: "nazwa", direction: "asc" }}
        onSortChange={sortowanie}
        selectedIds={[]}
        onSelectionChange={zaznaczenie}
        columns={[
          { key: "nazwa", label: "Nazwa", sortable: true, render: (wiersz) => wiersz.nazwa },
          { key: "rozmiar", label: "Rozmiar", numeric: true, render: (wiersz) => wiersz.rozmiar },
        ]}
      />,
    );
    const naglowek = screen.getByRole("columnheader", { name: /Nazwa/ });
    expect(naglowek.getAttribute("aria-sort")).toBe("ascending");
    fireEvent.click(within(naglowek).getByRole("button"));
    expect(sortowanie).toHaveBeenCalledWith({ key: "nazwa", direction: "desc" });

    fireEvent.click(screen.getByRole("checkbox", { name: "Zaznacz wszystkie wiersze" }));
    expect(zaznaczenie).toHaveBeenCalledWith(["1", "2"]);
  });

  it("pokazuje pusty stan zamiast wierszy", () => {
    render(
      <Table
        label="Pliki"
        rows={[]}
        rowId={(wiersz: { id: string }) => wiersz.id}
        columns={[{ key: "nazwa", label: "Nazwa", render: () => null }]}
        empty={<EmptyState title="Brak plików" description="Prześlij pierwszy plik." />}
      />,
    );
    expect(screen.getByText("Brak plików")).toBeTruthy();
  });
});

describe("Dialog", () => {
  it("ma rolę alertdialog, tytuł i potwierdzenie", () => {
    const potwierdz = vi.fn();
    const zmianaOtwarcia = vi.fn();
    render(
      <Dialog
        open
        onOpenChange={zmianaOtwarcia}
        variant="destructive"
        title="Usunąć 3 pliki na stałe?"
        description="Tej zmiany nie da się cofnąć."
        confirmLabel="Usuń 3 pliki"
        onConfirm={potwierdz}
      />,
    );
    expect(screen.getByRole("alertdialog", { name: "Usunąć 3 pliki na stałe?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Usuń 3 pliki" }));
    expect(potwierdz).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Anuluj" }));
    expect(zmianaOtwarcia).toHaveBeenCalledWith(false);
  });

  it("blokuje potwierdzenie do wpisania frazy", () => {
    const potwierdz = vi.fn();
    render(
      <Dialog open onOpenChange={() => {}} variant="destructive" title="Usunąć projekt?" confirmPhrase="usuń" confirmLabel="Usuń projekt" onConfirm={potwierdz} />,
    );
    const przycisk = screen.getByRole("button", { name: "Usuń projekt" });
    expect(przycisk.getAttribute("aria-disabled")).toBe("true");
    fireEvent.change(screen.getByLabelText(/Wpisz/), { target: { value: "usuń" } });
    fireEvent.click(screen.getByRole("button", { name: "Usuń projekt" }));
    expect(potwierdz).toHaveBeenCalledTimes(1);
  });
});

describe("Sheet", () => {
  it("ma tytuł i zamyka się przyciskiem", () => {
    const zmiana = vi.fn();
    render(
      <Sheet open onOpenChange={zmiana} title="Szczegóły pliku">
        <p>Treść panelu</p>
      </Sheet>,
    );
    expect(screen.getByText("Szczegóły pliku")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zamknij panel" }));
    expect(zmiana).toHaveBeenCalledWith(false);
  });
});

describe("Toast", () => {
  function Próbka() {
    const dymki = useToast();
    return (
      <button type="button" onClick={() => dymki.show({ variant: "error", title: "Nie udało się wczytać plików" })}>
        Pokaż
      </button>
    );
  }

  it("ogłasza błąd w roli alert", () => {
    render(
      <ToastProvider>
        <Próbka />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Pokaż" }));
    const dymek = screen.getByRole("alert");
    expect(dymek.textContent).toContain("Nie udało się wczytać plików");
    fireEvent.click(screen.getByRole("button", { name: "Zamknij powiadomienie" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("postęp i szkielet", () => {
  it("Progress podaje wartość i opis", () => {
    render(<Progress value={0.62} label="Przesyłanie 3 plików" valueText="62%" />);
    const pasek = screen.getByRole("progressbar");
    expect(pasek.getAttribute("aria-valuenow")).toBe("62");
    expect(pasek.getAttribute("aria-valuetext")).toBe("62%");
  });

  it("Progress nieokreślony nie podaje wartości", () => {
    render(<Progress valueText="Sprawdzam plik" />);
    expect(screen.getByRole("progressbar").hasAttribute("aria-valuenow")).toBe(false);
  });

  it("ProgressRing i Spinner mają nazwy dostępne", () => {
    const { container } = render(
      <>
        <ProgressRing value={0.25} label="Przesyłanie załącznika" />
        <Spinner label="Wczytywanie" />
        <Skeleton lines={3} />
      </>,
    );
    expect(screen.getByRole("progressbar", { name: "Przesyłanie załącznika" })).toBeTruthy();
    expect(screen.getByRole("status", { name: "Wczytywanie" })).toBeTruthy();
    expect(container.querySelectorAll(".ui-szkielet")).toHaveLength(3);
  });
});

describe("Badge i Tag", () => {
  it("Badge skraca licznik powyżej 99", () => {
    render(<Badge count={128} />);
    expect(screen.getByText("99+")).toBeTruthy();
  });

  it("Tag zgłasza stan filtru i usuwanie", () => {
    const usun = vi.fn();
    render(<Tag label="OCR" active onClick={() => {}} onRemove={usun} />);
    expect(screen.getByRole("button", { name: "OCR" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Usuń: OCR" }));
    expect(usun).toHaveBeenCalledTimes(1);
  });
});

describe("AgentStatus", () => {
  const praca: AgentRun = {
    id: "praca-1",
    state: "running",
    startedAt: new Date().toISOString(),
    steps: [
      { id: "1", label: "Analizuję dokument", state: "done", durationMs: 1200 },
      { id: "2", label: "Wykonuję OCR…", state: "running", progress: 0.62, detail: "Tesseract · język polski · 62%", tool: "tesseract" },
      { id: "3", label: "Odczytuję NIP i kwotę brutto", state: "queued" },
    ],
  };

  it("pokazuje krok bieżący, zegar i zatrzymanie", () => {
    const stop = vi.fn();
    render(<AgentStatus run={praca} onStop={stop} />);
    const karta = screen.getByRole("status");
    expect(karta.textContent).toContain("krok 2 z 3");
    expect(karta.textContent).toContain("00:00");
    fireEvent.click(screen.getByRole("button", { name: /Zatrzymaj/ }));
    expect(stop).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("62");
  });

  it("zwija i rozwija listę kroków", () => {
    render(<AgentStatus run={praca} onStop={() => {}} />);
    const zwin = screen.getByRole("button", { name: "Zwiń kroki" });
    expect(zwin.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(zwin);
    expect(screen.getByRole("button", { name: "Rozwiń kroki" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("błąd ogłasza się jako alert i daje ponowienie", () => {
    const ponow = vi.fn();
    render(
      <AgentStatus
        run={{ ...praca, state: "error", steps: [{ id: "1", label: "Wykonuję OCR…", state: "error", error: { message: "Za mało pamięci." } }] }}
        onStop={() => {}}
        onRetryStep={ponow}
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain("Krok nie powiódł się");
    fireEvent.click(screen.getByRole("button", { name: "Ponów krok" }));
    expect(ponow).toHaveBeenCalledWith("1");
  });
});

describe("BeforeAfterCompare", () => {
  it("uchwyt jest suwakiem sterowanym klawiaturą", () => {
    function Próbka() {
      const [podzial, setPodzial] = useState(0.5);
      return (
        <BeforeAfterCompare
          beforeUrl="/przed.png"
          afterUrl="/po.png"
          beforeAlt="Skan przed poprawą"
          afterAlt="Skan po poprawie"
          position={podzial}
          onPositionChange={setPodzial}
        />
      );
    }
    render(<Próbka />);
    const uchwyt = screen.getByRole("slider", { name: "Podział porównania" });
    expect(uchwyt.getAttribute("aria-valuenow")).toBe("50");
    fireEvent.keyDown(uchwyt, { key: "ArrowRight" });
    expect(uchwyt.getAttribute("aria-valuenow")).toBe("55");
    fireEvent.keyDown(uchwyt, { key: "End" });
    expect(uchwyt.getAttribute("aria-valuenow")).toBe("100");
    expect(screen.getByAltText("Skan przed poprawą")).toBeTruthy();
  });
});

describe("CommandPalette", () => {
  const pozycje: CommandItem[] = [
    { id: "plik-1", group: "files", label: "umowa-najmu-lokalu.pdf", onRun: () => {} },
    { id: "polecenie-1", group: "commands", label: "Wykonaj OCR", onRun: () => {} },
  ];

  function Próbka({ onRun, onAsk }: { onRun: () => void; onAsk: (zapytanie: string) => void }) {
    const [zapytanie, setZapytanie] = useState("umowa");
    const [tryb, setTryb] = useState<"all" | "commands" | "files" | "projects" | "help">("all");
    return (
      <CommandPalette
        open
        onOpenChange={() => {}}
        mode={tryb}
        onModeChange={setTryb}
        query={zapytanie}
        onQueryChange={setZapytanie}
        items={pozycje.map((pozycja) => ({ ...pozycja, onRun }))}
        onAskAssistant={onAsk}
      />
    );
  }

  it("prowadzi wybór strzałkami i uruchamia pozycję", () => {
    const uruchom = vi.fn();
    render(<Próbka onRun={uruchom} onAsk={() => {}} />);
    const pole = screen.getByRole("combobox", { name: /Szukaj/ });
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(pole.getAttribute("aria-activedescendant")).toContain("plik-1");
    fireEvent.keyDown(pole, { key: "ArrowDown" });
    expect(pole.getAttribute("aria-activedescendant")).toContain("polecenie-1");
    fireEvent.keyDown(pole, { key: "Enter" });
    expect(uruchom).toHaveBeenCalledTimes(1);
  });

  it("Ctrl+Enter przekazuje zapytanie asystentowi", () => {
    const zapytaj = vi.fn();
    render(<Próbka onRun={() => {}} onAsk={zapytaj} />);
    fireEvent.keyDown(screen.getByRole("combobox", { name: /Szukaj/ }), { key: "Enter", ctrlKey: true });
    expect(zapytaj).toHaveBeenCalledWith("umowa");
  });

  it("wpisanie znaku trybu przełącza tryb", () => {
    render(<Próbka onRun={() => {}} onAsk={() => {}} />);
    const pole = screen.getByRole("combobox", { name: /Szukaj/ });
    fireEvent.change(pole, { target: { value: ">ocr" } });
    expect((pole as HTMLInputElement).value).toBe("ocr");
    expect(screen.getAllByText("Polecenia").length).toBeGreaterThan(1);
  });
});

describe("Stagger", () => {
  it("nadaje kolejnym dzieciom rosnące opóźnienie, najwyżej cztery kroki", () => {
    const { container } = render(
      <Stagger>
        {Array.from({ length: 6 }, (_, index) => (
          <p key={index}>Wiersz {index}</p>
        ))}
      </Stagger>,
    );
    const dzieci = [...container.querySelectorAll<HTMLElement>("p")];
    expect(dzieci[0]?.style.getPropertyValue("--ui-opoznienie")).toContain("* 0");
    expect(dzieci[3]?.style.getPropertyValue("--ui-opoznienie")).toContain("* 3");
    expect(dzieci[5]?.style.getPropertyValue("--ui-opoznienie")).toContain("* 4");
    expect(dzieci[0]?.className).toContain("ui-wejscie");
  });
});

describe("Field", () => {
  // `w-full` i podana obok `w-44` to dwie klasy tej samej warstwy: o zwycięzcy decyduje
  // kolejność w arkuszu, nie w atrybucie — i wygrywało `w-full`. Pasek wyboru języków
  // w Tłumaczu rozjeżdżał się przez to na komputerze na cztery kontrolki jedna pod drugą.
  const korzen = (container: HTMLElement) => container.firstElementChild as HTMLElement;

  it("bez własnej szerokości zajmuje całą szerokość rodzica", () => {
    const { container } = render(
      <Field id="a" label="A">
        <input id="a" />
      </Field>,
    );
    expect(korzen(container).className).toContain("w-full");
  });

  it("nie dokłada „w-full”, gdy szerokość podaje wywołujący", () => {
    const { container } = render(
      <Field id="b" label="B" className="w-44">
        <input id="b" />
      </Field>,
    );
    expect(korzen(container).className).toContain("w-44");
    expect(korzen(container).className).not.toContain("w-full");
  });

  it("uznaje też szerokość z układu elastycznego", () => {
    const { container } = render(
      <Field id="c" label="C" className="min-w-0 flex-1">
        <input id="c" />
      </Field>,
    );
    expect(korzen(container).className).not.toContain("w-full");
  });

  it("„min-w-0” samo w sobie szerokości nie ustala", () => {
    const { container } = render(
      <Field id="d" label="D" className="min-w-0">
        <input id="d" />
      </Field>,
    );
    expect(korzen(container).className).toContain("w-full");
  });
});
