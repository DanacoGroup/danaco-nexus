// Porównanie obrazu przed/po z przesuwanym suwakiem (mysz, dotyk, klawiatura).

import { useRef, useState, type PointerEvent } from "react";
import { clamp } from "./logic";

const CHECKERBOARD =
  "repeating-conic-gradient(color-mix(in srgb, var(--line) 80%, transparent) 0% 25%, transparent 0% 50%) 50% / 18px 18px";

export function BeforeAfter({ before, after, alt }: { before: string; after: string; alt: string }) {
  const [position, setPosition] = useState(50);
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const move = (event: PointerEvent) => {
    const rect = box.current?.getBoundingClientRect();
    if (!rect || !dragging.current) return;
    setPosition(clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100));
  };

  return (
    <div
      ref={box}
      className="relative mx-auto w-fit max-w-full touch-none overflow-hidden rounded-2xl border border-line select-none"
      style={{ background: CHECKERBOARD }}
      onPointerDown={(event) => {
        dragging.current = true;
        event.currentTarget.setPointerCapture(event.pointerId);
        move(event);
      }}
      onPointerMove={move}
      onPointerUp={() => (dragging.current = false)}
      onPointerCancel={() => (dragging.current = false)}
    >
      <img src={after} alt={`${alt} – po`} className="block max-h-[62vh] max-w-full" draggable={false} />
      <img
        src={before}
        alt={`${alt} – przed`}
        className="absolute inset-0 block h-full w-full object-contain"
        style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        draggable={false}
      />
      <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow-[0_0_6px_rgba(0,0,0,.5)]" style={{ left: `${position}%` }} />
      <div
        role="slider"
        tabIndex={0}
        aria-label="Porównanie przed i po"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(position)}
        className="absolute top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/70 bg-black/55 text-xs text-white shadow-lg focus-visible:outline-2 focus-visible:outline-accent"
        style={{ left: `${position}%` }}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") setPosition((value) => clamp(value - 5, 0, 100));
          if (event.key === "ArrowRight") setPosition((value) => clamp(value + 5, 0, 100));
        }}
      >
        ⇆
      </div>
      <span className="pointer-events-none absolute top-2 left-2 rounded-md bg-black/55 px-2 py-0.5 text-xs text-white">Przed</span>
      <span className="pointer-events-none absolute top-2 right-2 rounded-md bg-black/55 px-2 py-0.5 text-xs text-white">Po</span>
    </div>
  );
}
