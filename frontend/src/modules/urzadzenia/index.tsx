// Moduł „Urządzenia”: klucze urządzeń, parowanie telefonu kodem QR, powiadomienia push.

import type { NexusModule } from "../registry";
import { DevicesIcon } from "../../shell/icons";
import { DevicesPage } from "./DevicesPage";

export const module: NexusModule = {
  id: "urzadzenia",
  label: "Urządzenia",
  description: "Telefon, Nexus Desktop i rozszerzenie połączone z Nexusem; powiadomienia push",
  icon: DevicesIcon,
  order: 900,
  Page: DevicesPage,
};
