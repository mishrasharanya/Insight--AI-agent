import { NavLink, Outlet } from "react-router-dom";
import { ArrowLeft, LogIn, LogOut, MessageSquare, RefreshCw, ShieldCheck, Table2 } from "lucide-react";
import { useAuth } from "../lib/useAuth";

const NAV = [
  { to: "/app/chat", label: "Chat", icon: MessageSquare, testid: "nav-chat" },
  { to: "/app/data", label: "Data", icon: Table2, testid: "nav-data" },
  { to: "/app/sync", label: "Sync", icon: RefreshCw, testid: "nav-sync" },
  { to: "/app/privacy", label: "Privacy", icon: ShieldCheck, testid: "nav-privacy" },
];

export default function Layout() {
  const { user, login, logout, leaveTrial } = useAuth();

  const backToLanding = () => {
    leaveTrial();
    window.location.href = "/";
  };

  return (
    <div className="min-h-screen bg-[#f5f1e8] text-[#1a1a1a]">
      <aside className="fixed top-0 left-0 h-screen w-64 border-r border-[#1a1a1a]/10 flex flex-col" data-testid="app-sidebar">
        <div className="px-6 py-6 border-b border-[#1a1a1a]/10 flex items-center gap-3">
          <div className="w-2 h-2 bg-[#b8541f] rounded-full" />
          <span className="font-mono text-xs uppercase tracking-[0.2em]">InsightAI</span>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon, testid }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-[#1a1a1a] text-[#f5f1e8]" : "text-[#1a1a1a]/70 hover:bg-[#1a1a1a]/5"
                }`
              }
            >
              <Icon className="w-4 h-4" strokeWidth={1.5} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-[#1a1a1a]/10">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#1a1a1a]/50 mb-1">
            {user?.isGuest ? "You are in" : "Signed in"}
          </p>
          <p className="text-sm truncate mb-3" data-testid="sidebar-user-email">
            {user?.email || user?.name || "Account"}
          </p>
          {user?.isGuest && (
            <button
              onClick={backToLanding}
              data-testid="sidebar-back-landing-button"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[#1a1a1a]/70 hover:bg-[#1a1a1a]/5 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
              Back to landing
            </button>
          )}
          <button
            onClick={user?.isGuest ? () => login("/app/chat") : logout}
            data-testid={user?.isGuest ? "sidebar-signin-button" : "sidebar-logout-button"}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[#1a1a1a]/70 hover:bg-[#1a1a1a]/5 transition-colors"
          >
            {user?.isGuest ? (
              <LogIn className="w-4 h-4" strokeWidth={1.5} />
            ) : (
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
            )}
            {user?.isGuest ? "Sign in with Google" : "Log out"}
          </button>
        </div>
      </aside>

      <main className="ml-64 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
