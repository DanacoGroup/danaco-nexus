// Moduł Strony (Twórca stron): lista stron i edycja rozmową z podglądem na żywo.

import { useState } from "react";
import type { ModulePageProps, NexusModule } from "../registry";
import { GlobeIcon } from "../_tworczy/icons";
import { SiteEditor } from "./SiteEditor";
import { SiteList } from "./SiteList";

function SitesPage({ openConversation }: ModulePageProps) {
  const [open, setOpen] = useState<{ address: string; prompt?: string } | null>(null);
  if (open) {
    return (
      <SiteEditor
        key={open.address}
        address={open.address}
        firstPrompt={open.prompt}
        onBack={() => setOpen(null)}
        openConversation={openConversation}
      />
    );
  }
  return <SiteList onOpen={(address, prompt) => setOpen({ address, prompt })} />;
}

export const module: NexusModule = {
  id: "strony",
  label: "Strony",
  description: "Twórca stron WWW: opis → strona na żywo, wersje i publikacja pod adresem Nexusa.",
  icon: GlobeIcon,
  order: 60,
  Page: SitesPage,
};
