// Moduł „Urządzenia”: klucze urządzeń, parowanie telefonu kodem QR, powiadomienia push.

import type { NexusModule } from "../registry";
import { DevicesIcon } from "../../shell/icons";
import { DevicesPage } from "./DevicesPage";

export const module: NexusModule = {
  id: "urzadzenia",
  // Nazwa z paska nawigacji też otwiera moduł.
  aliasy: ["sprzet"],
  label: "Sprzęt",
  description: "Telefon, Nexus Desktop i rozszerzenie przeglądarki: połączenia, powiadomienia i nadane zgody.",
  icon: DevicesIcon,
  order: 900,
  Page: DevicesPage,
};
