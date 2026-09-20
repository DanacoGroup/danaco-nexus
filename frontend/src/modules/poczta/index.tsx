// Moduł Poczta: skrzynki podłączone przez użytkownika (IMAP/SMTP) – czytanie, odpowiedzi z Nexusem, wysyłanie po zatwierdzeniu.

import { MailIcon } from "../_biuro/icons";
import type { NexusModule } from "../registry";
import { PocztaPage } from "./PocztaPage";

export const module: NexusModule = {
  id: "poczta",
  label: "Poczta",
  description: "Skrzynka e-mail: czytanie, wyszukiwanie, odpowiedzi przygotowane przez Nexusa i wysyłanie po Twoim zatwierdzeniu.",
  icon: MailIcon,
  order: 41,
  Page: PocztaPage,
};
