// Moduł Cloud: chmura osobista (Nextcloud) wbudowana w aplikację.

import { CloudIcon } from "../../components/icons";
import type { NexusModule } from "../registry";
import { CloudPage } from "./CloudPage";

export const module: NexusModule = {
  id: "cloud",
  label: "Chmura",
  description: "Pliki w chmurze osobistej: foldery, wersje, udostępnianie linkiem, synchronizacja z komputerem i telefonem.",
  icon: CloudIcon,
  order: 40,
  Page: CloudPage,
};
