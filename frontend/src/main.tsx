import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { setupPwa } from "./pwa";
import { applyTheme, storedTheme } from "./theme";
import "./styles.css";

applyTheme(storedTheme());
setupPwa();

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
