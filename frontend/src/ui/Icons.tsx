// Zestaw ikon biblioteki: obrys currentColor, siatka 24 px, tokeny --icon-*.
// Komponenty przyjmują ikonę jako węzeł (prop `icon`), więc można podać dowolny rysunek.

import type { SVGProps } from "react";

type IkonaProps = SVGProps<SVGSVGElement> & { size?: number };

function Ikona({ size = 16, children, ...props }: IkonaProps) {
  return (
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
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const CheckIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M4 12.5 9 17.5 20 6.5" />
  </Ikona>
);
export const MinusIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M6 12h12" />
  </Ikona>
);
export const CloseIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Ikona>
);
export const ChevronDownIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M6 9.5 12 15.5 18 9.5" />
  </Ikona>
);
export const ChevronRightIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M9.5 6 15.5 12 9.5 18" />
  </Ikona>
);
export const SearchIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M16 16l4 4" />
  </Ikona>
);
export const StopIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" />
  </Ikona>
);
export const SuccessIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8 12.5 11 15.5 16 9" />
  </Ikona>
);
export const ErrorIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.2v.3" />
  </Ikona>
);
export const WarningIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M12 4 21 19H3L12 4Z" />
    <path d="M12 10v4M12 16.8v.3" />
  </Ikona>
);
export const InfoIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5.5M12 7.5v.3" />
  </Ikona>
);
export const CircleDashedIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <circle cx="12" cy="12" r="8.5" strokeDasharray="3 3.4" />
  </Ikona>
);
export const SparkleIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M12 4l1.9 4.9L18.8 11l-4.9 1.9L12 17.8l-1.9-4.9L5.2 11l4.9-2.1L12 4Z" />
  </Ikona>
);
export const CompareIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M12 4v16M8 8.5 4.5 12 8 15.5M16 8.5 19.5 12 16 15.5" />
  </Ikona>
);
export const FolderIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M3.5 7.5a2 2 0 0 1 2-2h3.2l2 2.4h7.8a2 2 0 0 1 2 2v7.6a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2v-10Z" />
  </Ikona>
);
export const SortIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M8 9.5 12 5.5 16 9.5M8 14.5 12 18.5 16 14.5" />
  </Ikona>
);
export const ArrowUpIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M12 19V6M6.5 11.5 12 6l5.5 5.5" />
  </Ikona>
);
export const ArrowDownIcon = (p: IkonaProps) => (
  <Ikona {...p}>
    <path d="M12 5v13M6.5 12.5 12 18l5.5-5.5" />
  </Ikona>
);
