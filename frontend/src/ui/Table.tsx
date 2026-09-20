// Tabela z sortowaniem i zaznaczaniem (ui-kit, rozdz. 6.1 — wersja ogólna).
// Kolumny liczbowe do prawej, cyfry tabelaryczne; wczytywanie przez szkielet.

import { useId, type ReactNode } from "react";
import { Checkbox } from "./Checkbox";
import { ArrowDownIcon, ArrowUpIcon, SortIcon } from "./Icons";
import { Skeleton } from "./Skeleton";
import { cx, type BaseProps } from "./types";

export interface TableColumn<T> {
  key: string;
  label: string;
  /** Wyrównanie do prawej i cyfry tabelaryczne. */
  numeric?: boolean;
  sortable?: boolean;
  width?: string;
  render: (row: T) => ReactNode;
}

export interface TableSort {
  key: string;
  direction: "asc" | "desc";
}

export interface TableProps<T> extends BaseProps {
  /** Nazwa dostępna tabeli. */
  label: string;
  columns: TableColumn<T>[];
  rows: T[];
  rowId: (row: T) => string;
  sort?: TableSort;
  onSortChange?: (sort: TableSort) => void;
  selectedIds?: string[];
  onSelectionChange?: (ids: string[]) => void;
  onOpen?: (row: T) => void;
  loading?: boolean;
  /** Pokazywany, gdy nie ma wierszy — zwykle EmptyState. */
  empty?: ReactNode;
  density?: "default" | "touch";
}

export function Table<T>({
  label,
  columns,
  rows,
  rowId,
  sort,
  onSortChange,
  selectedIds,
  onSelectionChange,
  onOpen,
  loading = false,
  empty,
  density = "default",
  className,
  ...reszta
}: TableProps<T>) {
  const id = useId();
  const zaznaczanie = Boolean(selectedIds && onSelectionChange);
  const zaznaczone = new Set(selectedIds ?? []);
  const wysokosc = density === "touch" ? "var(--control-xl)" : "var(--control-lg)";

  const wszystkie: boolean | "mixed" = !rows.length
    ? false
    : zaznaczone.size === rows.length
      ? true
      : zaznaczone.size === 0
        ? false
        : "mixed";

  const przelaczWszystkie = (stan: boolean) => onSelectionChange?.(stan ? rows.map(rowId) : []);

  const przelaczWiersz = (identyfikator: string, stan: boolean) => {
    const nowe = new Set(zaznaczone);
    if (stan) nowe.add(identyfikator);
    else nowe.delete(identyfikator);
    onSelectionChange?.([...nowe]);
  };

  const sortuj = (kolumna: TableColumn<T>) => {
    if (!kolumna.sortable || !onSortChange) return;
    const kierunek = sort?.key === kolumna.key && sort.direction === "asc" ? "desc" : "asc";
    onSortChange({ key: kolumna.key, direction: kierunek });
  };

  if (!loading && !rows.length && empty) {
    return (
      <div className={cx("overflow-hidden rounded-lg border border-line bg-raised", className)} {...reszta}>
        {empty}
      </div>
    );
  }

  return (
    <div className={cx("overflow-x-auto rounded-lg border border-line bg-raised", className)} {...reszta}>
      <table className="w-full border-collapse" aria-label={label} aria-busy={loading || undefined} aria-rowcount={rows.length}>
        <thead className="bg-side">
          <tr style={{ blockSize: "var(--control-md)" }}>
            {zaznaczanie ? (
              <th scope="col" style={{ inlineSize: "var(--control-lg)", paddingInline: "var(--space-3)" }}>
                <Checkbox checked={wszystkie} onChange={przelaczWszystkie} ariaLabel="Zaznacz wszystkie wiersze" />
              </th>
            ) : null}
            {columns.map((kolumna) => {
              const aktywna = sort?.key === kolumna.key;
              return (
                <th
                  key={kolumna.key}
                  scope="col"
                  aria-sort={aktywna ? (sort?.direction === "asc" ? "ascending" : "descending") : kolumna.sortable ? "none" : undefined}
                  className={cx("text-muted", kolumna.numeric ? "text-end" : "text-start")}
                  style={{
                    inlineSize: kolumna.width,
                    paddingInline: "var(--space-3)",
                    font: "var(--text-style-label)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  {kolumna.sortable ? (
                    <button
                      type="button"
                      onClick={() => sortuj(kolumna)}
                      className={cx("ui-przejscie inline-flex items-center", aktywna ? "text-fg" : "text-muted hover:text-fg")}
                      style={{ gap: "var(--space-1)" }}
                    >
                      {kolumna.label}
                      {aktywna ? sort?.direction === "asc" ? <ArrowUpIcon size={14} /> : <ArrowDownIcon size={14} /> : <SortIcon size={14} />}
                    </button>
                  ) : (
                    kolumna.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 4 }, (_, index) => (
                <tr key={`szkielet-${index}`} style={{ blockSize: wysokosc }}>
                  {zaznaczanie ? <td style={{ paddingInline: "var(--space-3)" }} /> : null}
                  {columns.map((kolumna) => (
                    <td key={kolumna.key} style={{ paddingInline: "var(--space-3)" }}>
                      <Skeleton />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((wiersz, index) => {
                const identyfikator = rowId(wiersz);
                const wybrany = zaznaczone.has(identyfikator);
                return (
                  <tr
                    key={identyfikator}
                    id={`${id}-${index}`}
                    aria-rowindex={index + 1}
                    aria-selected={zaznaczanie ? wybrany : undefined}
                    tabIndex={onOpen ? 0 : undefined}
                    onKeyDown={(zdarzenie) => {
                      if (zdarzenie.key === "Enter" && onOpen) onOpen(wiersz);
                      if (zdarzenie.key === " " && zaznaczanie) {
                        zdarzenie.preventDefault();
                        przelaczWiersz(identyfikator, !wybrany);
                      }
                    }}
                    onDoubleClick={() => onOpen?.(wiersz)}
                    className={cx("ui-przejscie border-t border-line", wybrany ? "bg-accent-soft" : "hover:bg-hover")}
                    style={{ blockSize: wysokosc }}
                  >
                    {zaznaczanie ? (
                      <td style={{ paddingInline: "var(--space-3)" }}>
                        <Checkbox
                          checked={wybrany}
                          onChange={(stan) => przelaczWiersz(identyfikator, stan)}
                          ariaLabel={`Zaznacz wiersz ${index + 1}`}
                        />
                      </td>
                    ) : null}
                    {columns.map((kolumna) => (
                      <td
                        key={kolumna.key}
                        className={cx("text-fg", kolumna.numeric ? "text-end" : "text-start")}
                        style={{
                          paddingInline: "var(--space-3)",
                          font: "var(--text-style-body)",
                          fontVariantNumeric: kolumna.numeric ? "var(--font-numeric-tabular)" : undefined,
                        }}
                      >
                        {kolumna.render(wiersz)}
                      </td>
                    ))}
                  </tr>
                );
              })}
        </tbody>
      </table>
    </div>
  );
}
