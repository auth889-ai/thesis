import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import React from "react";
import {createRoot} from "react-dom/client";
import {RouterProvider} from "react-router-dom";

import {router} from "./app/routes";
import {I18nProvider} from "./i18n";
import {CityProvider} from "./lib/city";
import "./styles/global.css";
import {registerSW} from "virtual:pwa-register";

const update = registerSW({immediate: true, onNeedRefresh: () => window.dispatchEvent(new Event("tt-update-ready"))});   // the offline shell (Workbox); a new version waits for the person (app/UpdateBar)
(window as any).ttUpdate = () => update(true);

const queryClient = new QueryClient({defaultOptions: {queries: {retry: 1, staleTime: 30_000, refetchOnWindowFocus: false}}});

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider><CityProvider><RouterProvider router={router} /></CityProvider></I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
