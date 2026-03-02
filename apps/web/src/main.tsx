import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { WarRoomPage } from "./pages/WarRoomPage";

const params = new URLSearchParams(window.location.search);
const sessionId = params.get("sessionId") ?? "replace-with-session-id";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing root element");
}

createRoot(rootEl).render(
  <StrictMode>
    <WarRoomPage sessionId={sessionId} />
  </StrictMode>
);
