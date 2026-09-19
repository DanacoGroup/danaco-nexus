import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { setupPwa } from "./pwa";
import { applyTheme, storedTheme } from "./theme";
import "./styles.css";

applyTheme(storedTheme());
// Panel osadzony (?widok=panel) nie rejestruje service workera – działa w ramce cudzej strony.
if (new URLSearchParams(window.location.search).get("widok") !== "panel") setupPwa();

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
