import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ComparisonPage } from "./pages/ComparisonPage";
import { WarRoomPage } from "./pages/WarRoomPage";

const params = new URLSearchParams(window.location.search);
const view = params.get("view") ?? "comparison";
const sessionId = params.get("sessionId") ?? "replace-with-session-id";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing root element");
}

const page = view === "warroom" ? <WarRoomPage sessionId={sessionId} /> : <ComparisonPage />;

createRoot(rootEl).render(<StrictMode>{page}</StrictMode>);
