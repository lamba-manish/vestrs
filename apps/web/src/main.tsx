import "@fontsource-variable/inter";
import "@fontsource-variable/fraunces";
import "./styles/globals.css";

import * as React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "@/App";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("#root not found in index.html");
}

createRoot(container).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
