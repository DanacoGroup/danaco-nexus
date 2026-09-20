// Przypisanie nagrań z pakietu ruchu (motion/stany) do narzędzi agenta.
//
// Rodzina „praca agenta według narzędzia” z motion/stany/README.md powstała dokładnie
// po to, żeby pokazywać, co robi dane narzędzie. Tu jest miejsce, w którym nagranie
// spotyka się z narzędziem; katalog ścieżek generuje frontend/scripts/zasoby.py.

import { STANY } from "../../media/katalog";

/** Identyfikator nagrania stanu — typ pilnuje, żeby przypisanie nie wskazywało na nieistniejące ujęcie. */
type IdStanu = (typeof STANY)[number]["id"];

/** Narzędzie → identyfikator nagrania w `STANY`. */
const PRZYPISANIE: Record<string, IdStanu> = {
  colorize_photo: "odnawianie",
  find_faces: "odnawianie",
  animate_photo: "ilustracja",
  clean_audio: "transkrypcja",
  split_audio_tracks: "transkrypcja",
  design_vector: "ilustracja",
  design_compose: "ilustracja",
  enhance_photo: "odnawianie",
  retouch_portrait: "odnawianie",
  upscale_image: "powiekszanie",
  remove_background: "tlo",
  change_background: "tlo",
  erase_objects: "tlo",
  convert_images: "ilustracja",
  imagemagick: "ilustracja",
  ocr_documents: "ocr",
  enhance_document_scan: "ocr",
  detect_document_boundaries: "ocr",
  extract_text: "czytanie",
  view_pages: "czytanie",
  write_document: "czytanie",
  translate_document: "czytanie",
  check_grammar: "czytanie",
  index_documents: "wiedza",
  search_documents: "wiedza",
  knowledge_save: "wiedza",
  knowledge_read: "wiedza",
  knowledge_notes: "wiedza",
  web_search: "wycieczka",
  web_fetch_page: "wycieczka",
  scholar_search: "wycieczka",
  scholar_paper: "wycieczka",
  transcribe_audio: "transkrypcja",
  media_process: "transkrypcja",
  mail_draft: "automatyzacja",
  mail_send: "automatyzacja",
  calendar_create: "automatyzacja",
  calendar_update: "automatyzacja",
  cloud_save: "synchronizacja",
  cloud_import: "synchronizacja",
  cloud_browse: "synchronizacja",
  create_archive: "przesylanie",
  extract_archive: "przesylanie",
  site_publish: "sukces",
  pc_screenshot: "podglad-pliku",
  convert_documents: "czytanie",
  pdf_merge: "szuflada",
  pdf_split: "szuflada",
  pdf_edit_pages: "szuflada",
  inspect_files: "podglad-pliku",
  mail_list: "widoki",
  mail_read: "widoki",
  mail_search: "widoki",
  calendar_list: "widoki",
  site_list: "widoki",
  site_read_file: "widoki",
  site_write_file: "przesylanie",
  site_import_file: "przesylanie",
  site_save_version: "przypiecie",
  pc_info: "polaczenie",
  pc_find_files: "podglad-pliku",
  pc_read_file: "podglad-pliku",
  pc_powershell: "automatyzacja",
};

const PO_ID = new Map<IdStanu, (typeof STANY)[number]>(STANY.map((nagranie) => [nagranie.id, nagranie]));

/** Nagranie pokazujące pracę danego narzędzia albo `null`, gdy takiego nie nagrano. */
export function nagranieNarzedzia(idNarzedzia: string): { mp4?: string; webm?: string } | null {
  const nazwa = PRZYPISANIE[idNarzedzia];
  if (!nazwa) return null;
  return PO_ID.get(nazwa)?.zrodla ?? null;
}
