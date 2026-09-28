import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import React from "react";
import {createRoot} from "react-dom/client";
import {RouterProvider} from "react-router-dom";

import {router} from "./app/routes";
import "./styles/global.css";

const queryClient = new QueryClient({defaultOptions: {queries: {retry: 1, staleTime: 30_000, refetchOnWindowFocus: false}}});

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
