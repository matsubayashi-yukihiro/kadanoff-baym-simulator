import { Outlet } from "react-router-dom";

import { NavTabs } from "./NavTabs";
import { TopBar } from "./TopBar";

export function AppShell() {
  return (
    <div className="flex flex-col min-h-screen">
      <TopBar />
      <NavTabs />
      <div className="flex flex-1 min-h-0 max-w-page mx-auto w-full">
        <Outlet />
      </div>
    </div>
  );
}
