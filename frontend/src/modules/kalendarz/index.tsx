// Moduł Kalendarz: kalendarz chmury (CalDAV) z planowaniem przez Nexusa.

import { CalendarIcon } from "../_biuro/icons";
import type { NexusModule } from "../registry";
import { KalendarzPage } from "./KalendarzPage";

export const module: NexusModule = {
  id: "kalendarz",
  label: "Kalendarz",
  description: "Terminy i spotkania: widok tygodnia i miesiąca, planowanie z Nexusem, synchronizacja z telefonem w planach Pro i Grupa.",
  icon: CalendarIcon,
  order: 42,
  Page: KalendarzPage,
};
