// Kod QR jako SVG (biblioteka qrcode-generator, bez zapytań do zewnętrznych usług).

import qrcode from "qrcode-generator";
import { useMemo } from "react";

export function qrMatrix(text: string): boolean[][] {
  const code = qrcode(0, "M");
  code.addData(text, "Byte");
  code.make();
  const size = code.getModuleCount();
  return Array.from({ length: size }, (_, row) => Array.from({ length: size }, (_, col) => code.isDark(row, col)));
}

export function QrCode({ text, size = 200, label }: { text: string; size?: number; label: string }) {
  const matrix = useMemo(() => qrMatrix(text), [text]);
  const count = matrix.length;
  const margin = 4;
  const path = matrix
    .flatMap((row, y) => row.map((dark, x) => (dark ? `M${x + margin} ${y + margin}h1v1h-1z` : "")))
    .join("");
  return (
    <svg
      role="img"
      aria-label={label}
      width={size}
      height={size}
      viewBox={`0 0 ${count + margin * 2} ${count + margin * 2}`}
      shapeRendering="crispEdges"
      className="rounded-xl"
    >
      <rect width="100%" height="100%" fill="#ffffff" />
      <path d={path} fill="#111113" />
    </svg>
  );
}
