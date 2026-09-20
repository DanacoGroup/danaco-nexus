// Porównanie przed i po (ui-kit, rozdz. 12.3). Uchwyt jest suwakiem: strzałki
// przesuwają o 5%, Home i End do krańców.

import { useCallback, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Badge } from "./Badge";
import { CompareIcon } from "./Icons";
import { cx, type BaseProps } from "./types";

export interface BeforeAfterCompareProps extends BaseProps {
  beforeUrl: string;
  afterUrl: string;
  beforeAlt: string;
  afterAlt: string;
  /** 0–1; bez wartości komponent prowadzi własny stan. */
  position?: number;
  onPositionChange?: (position: number) => void;
  /** Tylko wynik — uchwyt ukryty. */
  resultOnly?: boolean;
  /** Wysokość obszaru; domyślnie połowa panelu szerokiego (280 px). */
  height?: string;
}

const KROK = 0.05;

export function BeforeAfterCompare({
  beforeUrl,
  afterUrl,
  beforeAlt,
  afterAlt,
  position,
  onPositionChange,
  resultOnly = false,
  height = "calc(var(--layout-panel-wide) / 2)",
  className,
  ...reszta
}: BeforeAfterCompareProps) {
  const id = useId();
  const [wlasna, setWlasna] = useState(0.5);
  const obszar = useRef<HTMLDivElement>(null);
  const podzial = position ?? wlasna;

  const ustaw = useCallback(
    (wartosc: number) => {
      const ograniczona = Math.min(1, Math.max(0, wartosc));
      setWlasna(ograniczona);
      onPositionChange?.(ograniczona);
    },
    [onPositionChange],
  );

  const zWskaznika = (zdarzenie: PointerEvent<HTMLElement>) => {
    const ramka = obszar.current?.getBoundingClientRect();
    if (!ramka || ramka.width === 0) return;
    ustaw((zdarzenie.clientX - ramka.left) / ramka.width);
  };

  const klawisz = (zdarzenie: KeyboardEvent) => {
    if (zdarzenie.key === "ArrowLeft") ustaw(podzial - KROK);
    else if (zdarzenie.key === "ArrowRight") ustaw(podzial + KROK);
    else if (zdarzenie.key === "Home") ustaw(0);
    else if (zdarzenie.key === "End") ustaw(1);
    else return;
    zdarzenie.preventDefault();
  };

  const procent = Math.round(podzial * 100);

  return (
    <div
      ref={obszar}
      className={cx("relative select-none overflow-hidden rounded-lg bg-side", className)}
      style={{ blockSize: height }}
      {...reszta}
    >
      <img src={afterUrl} alt={afterAlt} className="absolute inset-0 h-full w-full object-contain" />
      {!resultOnly ? (
        <img
          src={beforeUrl}
          alt={beforeAlt}
          className="absolute inset-0 h-full w-full object-contain"
          style={{ clipPath: `inset(0 ${100 - procent}% 0 0)` }}
        />
      ) : null}

      <span className="absolute" style={{ insetBlockStart: "var(--space-3)", insetInlineStart: "var(--space-3)" }}>
        <Badge tone="neutral">Przed</Badge>
      </span>
      <span className="absolute" style={{ insetBlockStart: "var(--space-3)", insetInlineEnd: "var(--space-3)" }}>
        <Badge tone="ai">Po</Badge>
      </span>

      {!resultOnly ? (
        <div
          id={id}
          role="slider"
          tabIndex={0}
          aria-label="Podział porównania"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={procent}
          aria-valuetext={`${procent}% — po lewej przed, po prawej po`}
          onKeyDown={klawisz}
          onPointerDown={(zdarzenie) => {
            zdarzenie.currentTarget.setPointerCapture(zdarzenie.pointerId);
            zWskaznika(zdarzenie);
          }}
          onPointerMove={(zdarzenie) => zdarzenie.currentTarget.hasPointerCapture(zdarzenie.pointerId) && zWskaznika(zdarzenie)}
          className="ui-porownanie-uchwyt absolute inset-y-0 grid place-items-center"
          style={{ insetInlineStart: `${procent}%`, inlineSize: "var(--control-md)", transform: "translateX(-50%)" }}
        >
          <span
            className="absolute inset-y-0 bg-[color:var(--color-white)] shadow-medium"
            style={{ inlineSize: "var(--border-width-thick)" }}
          />
          <span
            className="relative grid place-items-center rounded-full bg-[color:var(--color-white)] text-[color:var(--color-brand-ink)] shadow-medium"
            style={{ inlineSize: "var(--space-8)", blockSize: "var(--space-8)" }}
          >
            <CompareIcon />
          </span>
        </div>
      ) : null}
    </div>
  );
}
