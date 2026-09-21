// Moduł Cloud: chmura osobista (Nextcloud) wbudowana w aplikację.

import { CloudIcon } from "../../components/icons";
import type { NexusModule } from "../registry";
import { CloudPage } from "./CloudPage";

export const module: NexusModule = {
  id: "cloud",
  // Polska nazwa z paska nawigacji też otwiera moduł.
  aliasy: ["chmura"],
  label: "Chmura",
  description:
    "Twoja przestrzeń w chmurze — sąsiad zakładki Pliki: wersje, udostępnianie linkiem " +
    "i synchronizacja z komputerem oraz telefonem.",
  icon: CloudIcon,
  order: 16,
  Page: CloudPage,
};
