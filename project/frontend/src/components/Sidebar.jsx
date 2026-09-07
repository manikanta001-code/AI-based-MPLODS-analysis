import { NavLink } from "react-router-dom";
import { LayoutDashboard, AlertTriangle, UploadCloud, FolderSearch, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const ROLE_HOME = {
  ministry: "/ministry",
  state: "/state",
  mp: "/mp",
  district: "/district",
};

const ROLE_LABEL = {
  ministry: "Ministry",
  state: "State Nodal",
  mp: "Member of Parliament",
  district: "District",
};

export default function Sidebar() {
  const { user, displayName, logout } = useAuth();
  if (!user) return null;

  const homePath = ROLE_HOME[user.role] || "/";

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
      isActive ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
    }`;

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-ink flex flex-col">
      <div className="px-5 py-6 border-b border-white/10">
        <div className="font-display text-lg text-white leading-tight">MPLADS Monitor</div>
        <div className="text-xs text-white/50 mt-0.5">AI Oversight Platform</div>
      </div>

      <nav className="flex-1 py-4 flex flex-col gap-1">
        <NavLink to={homePath} end className={linkClass}>
          <LayoutDashboard size={16} strokeWidth={1.75} />
          Dashboard
        </NavLink>
        <NavLink to="/works" className={linkClass}>
          <FolderSearch size={16} strokeWidth={1.75} />
          Works
        </NavLink>
        <NavLink to="/alerts" className={linkClass}>
          <AlertTriangle size={16} strokeWidth={1.75} />
          Alerts
        </NavLink>
        {(user.role === "ministry" || user.role === "state") && (
          <NavLink to="/upload" className={linkClass}>
            <UploadCloud size={16} strokeWidth={1.75} />
            Upload Data
          </NavLink>
        )}
      </nav>

      <div className="px-5 py-4 border-t border-white/10">
        <div className="text-sm text-white leading-tight">{displayName || user.username}</div>
        <div className="text-xs text-white/50 mt-0.5">
          {ROLE_LABEL[user.role]}
          {user.scope ? ` · ${user.scope.split("(")[0]}` : ""}
        </div>
        <button
          onClick={logout}
          className="mt-3 flex items-center gap-2 text-xs text-white/60 hover:text-white transition-colors"
        >
          <LogOut size={13} strokeWidth={1.75} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
