// Ikony SVG (obrys 1.75 px, kolor z currentColor).

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 20, children, ...props }: IconProps) {
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
      {...props}
    >
      {children}
    </svg>
  );
}

export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const SendIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </Icon>
);
export const StopIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" />
  </Icon>
);
export const PaperclipIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 11.5 12.5 20a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8" />
  </Icon>
);
export const MenuIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Icon>
);
export const CloseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
);
export const DownloadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </Icon>
);
export const EyeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </Icon>
);
export const FileIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </Icon>
);
export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12.5 10 17 19 7" />
  </Icon>
);
export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.5v.01" />
  </Icon>
);
export const ToolIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14.7 6.3a4 4 0 0 0 5 5L21 13l-8 8-3-3 1.3-1.3a4 4 0 0 0-5-5L3 10l8-8 3 3z" />
  </Icon>
);
export const ChevronIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
);
export const TrashIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
  </Icon>
);
export const EditIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20h4L19 9l-4-4L4 16z" />
  </Icon>
);
export const LogoutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4M6 12h10" />
  </Icon>
);
export const SparkIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
  </Icon>
);
export const CloudIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4.75 4.75 0 0 1-.25 9.5H7Z" />
  </Icon>
);
export const SunIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icon>
);
export const MoonIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
  </Icon>
);
export const MonitorIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M8 20h8M12 16v4" />
  </Icon>
);
export const InstallIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
    <path d="M12 7v7M9 11l3 3 3-3M10 18.5h4" />
  </Icon>
);
export const RefreshIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" />
  </Icon>
);
export const ShareIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v12M8 7l4-4 4 4M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" />
  </Icon>
);

/** Znak Danaco Nexus — sygnet z pakietu marki (logo/svg/symbol.svg). */
export function Logo({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <img
      src="/znak/symbol.svg"
      width={size}
      height={size}
      // Rozmiar wprost: reset Tailwind ustawia img {height:auto}, przez co znak rozciągał się w kolumnie.
      style={{ width: size, height: size }}
      className={`block shrink-0 ${className}`}
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}

/** Sam znak (łuk z punktem) w kolorze tekstu — do pasków, przycisków i druku jednobarwnego. */
export function Mark({ size = 20, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={(size * 50) / 53}
      height={size}
      viewBox="0 0 50 53"
      className={className}
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M0 47V25A25 25 0 0 1 50 25V47A6 6 0 0 1 38 47V25A13 13 0 0 0 12 25V47A6 6 0 0 1 0 47ZM18.5 25A6.5 6.5 0 1 0 31.5 25A6.5 6.5 0 1 0 18.5 25Z" />
    </svg>
  );
}

/** Logotyp poziomy (znak i napis) — wariant dobrany do motywu klasą `.dark`. */
export function Logotype({ height = 24, className = "" }: { height?: number; className?: string }) {
  return (
    <span className={`inline-flex ${className}`} style={{ height }}>
      <img src="/znak/logo-poziome-jasny.svg" style={{ height }} className="dark:hidden" alt="Danaco Nexus" draggable={false} />
      <img src="/znak/logo-poziome-ciemny.svg" style={{ height }} className="hidden dark:block" alt="Danaco Nexus" draggable={false} />
    </span>
  );
}

export const WaveIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" />
  </Icon>
);
export const MicIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </Icon>
);
