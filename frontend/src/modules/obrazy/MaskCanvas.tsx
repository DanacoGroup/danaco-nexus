// Płótno gumki: pędzel zaznacza obszar do usunięcia na obrazie (maska w rozdzielczości obrazu).

import { forwardRef, useImperativeHandle, useRef, useState, type PointerEvent } from "react";

export interface MaskHandle {
  /** Maska PNG (data URL): zamalowane piksele = obszar do usunięcia. */
  toDataUrl: () => string | null;
  clear: () => void;
}

export const MaskCanvas = forwardRef<MaskHandle, { src: string; brush: number; onChange: (empty: boolean) => void }>(
  function MaskCanvas({ src, brush, onChange }, ref) {
    const canvas = useRef<HTMLCanvasElement>(null);
    const drawing = useRef(false);
    const last = useRef<{ x: number; y: number } | null>(null);
    const [painted, setPainted] = useState(false);

    useImperativeHandle(ref, () => ({
      toDataUrl: () => (painted && canvas.current ? canvas.current.toDataURL("image/png") : null),
      clear: () => {
        const element = canvas.current;
        element?.getContext("2d")?.clearRect(0, 0, element.width, element.height);
        setPainted(false);
        onChange(true);
      },
    }));

    const point = (event: PointerEvent<HTMLCanvasElement>) => {
      const element = event.currentTarget;
      const rect = element.getBoundingClientRect();
      const scale = element.width / rect.width;
      return { x: (event.clientX - rect.left) * scale, y: (event.clientY - rect.top) * scale, scale };
    };

    const paint = (event: PointerEvent<HTMLCanvasElement>) => {
      const context = event.currentTarget.getContext("2d");
      if (!context || !drawing.current) return;
      const { x, y, scale } = point(event);
      context.strokeStyle = "#ff2d55";
      context.fillStyle = "#ff2d55";
      context.lineCap = "round";
      context.lineJoin = "round";
      context.lineWidth = brush * scale;
      const from = last.current ?? { x, y };
      context.beginPath();
      context.moveTo(from.x, from.y);
      context.lineTo(x, y);
      context.stroke();
      context.beginPath();
      context.arc(x, y, (brush * scale) / 2, 0, Math.PI * 2);
      context.fill();
      last.current = { x, y };
      if (!painted) {
        setPainted(true);
        onChange(false);
      }
    };

    return (
      <div className="relative mx-auto w-fit max-w-full overflow-hidden rounded-2xl border border-line">
        <img
          src={src}
          alt="Obraz do edycji"
          className="block max-h-[62vh] max-w-full select-none"
          draggable={false}
          onLoad={(event) => {
            const image = event.currentTarget;
            if (canvas.current) {
              canvas.current.width = image.naturalWidth;
              canvas.current.height = image.naturalHeight;
              setPainted(false);
              onChange(true);
            }
          }}
        />
        <canvas
          ref={canvas}
          aria-label="Zamaluj obszar do usunięcia"
          className="absolute inset-0 h-full w-full cursor-crosshair touch-none opacity-55"
          onPointerDown={(event) => {
            drawing.current = true;
            last.current = null;
            event.currentTarget.setPointerCapture(event.pointerId);
            paint(event);
          }}
          onPointerMove={paint}
          onPointerUp={() => {
            drawing.current = false;
            last.current = null;
          }}
          onPointerCancel={() => {
            drawing.current = false;
            last.current = null;
          }}
        />
      </div>
    );
  },
);
