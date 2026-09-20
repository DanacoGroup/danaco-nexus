// Ikona modułu „Możliwości”: iskra — to samo znaczenie, co punkt Aurory w znaku marki.

import type { SVGProps } from "react";

export const SparkIcon = ({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M12 3.5 13.9 9 19.5 10.9 13.9 12.8 12 18.3 10.1 12.8 4.5 10.9 10.1 9Z" />
    <path d="M18.5 16.5 19.2 18.3 21 19 19.2 19.7 18.5 21.5 17.8 19.7 16 19 17.8 18.3Z" />
  </svg>
);
