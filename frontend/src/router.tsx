import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { SingleJobPage } from "./pages/SingleJobPage";
import { CompareJobsPage } from "./pages/CompareJobsPage";
import { ParameterSweepPage } from "./pages/ParameterSweepPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<SingleJobPage />} />
          <Route path="compare-jobs" element={<CompareJobsPage />} />
          <Route path="parameter-sweep" element={<ParameterSweepPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
