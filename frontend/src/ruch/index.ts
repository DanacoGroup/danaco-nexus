// Warstwa ruchu strony produktu i portalu. Arkusze wpina `src/styles.css`.

export { PasSwitu, TloNaZywo, WarstwaZiarna, type PasSwituProps, type TloNaZywoProps } from "./TloNaZywo";
export { ZnakRuchu, type MomentZnaku, type ZnakRuchuProps } from "./ZnakRuchu";
export { PrzejscieWidoku, type PrzejscieWidokuProps } from "./PrzejscieWidoku";
export { EkranPrzejscia, type EkranPrzejsciaProps } from "./EkranPrzejscia";
export { kaskada, useOdtwarzajWWidoku, useWidocznosc } from "./wejscia";
export { otwarcieZagra, useOtwarcie } from "./otwarcie";
export {
  klatkaZastepcza,
  wczytajTlo,
  type ModulTla,
  type NazwaTla,
  type NazwaTlaWebGL,
  type UchwytTla,
} from "./tla";
export {
  NagranieStartu,
  zrodlaStartu,
  type IdStartu,
  type NagranieStartuProps,
} from "./NagranieStartu";
// Ograniczony ruch mieszka przy preferencjach konta — to jedno źródło dla skryptu i CSS.
export { ograniczonyRuch, zastosujRuch } from "../preferencje";
export { NagranieStanu, zrodlaStanu, type IdStanu, type NagranieStanuProps } from "./NagranieStanu";
