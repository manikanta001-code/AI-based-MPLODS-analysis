import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Sidebar from "./components/Sidebar";

import Login from "./pages/Login";
import MinistryDashboard from "./pages/MinistryDashboard";
import StateDashboard from "./pages/StateDashboard";
import MPDashboard from "./pages/MPDashboard";
import DistrictDashboard from "./pages/DistrictDashboard";
import Alerts from "./pages/Alerts";
import UploadData from "./pages/UploadData";
import ProjectDetail from "./pages/ProjectDetail";
import WorksExplorer from "./pages/WorksExplorer";

const ROLE_HOME = { ministry: "/ministry", state: "/state", mp: "/mp", district: "/district" };

function AppShell({ children }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <main className="ml-60 px-8 py-8 max-w-6xl">{children}</main>
    </div>
  );
}

export default function App() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={ROLE_HOME[user.role] || "/works"} replace /> : <Login />} />

      <Route
        path="/ministry"
        element={
          <ProtectedRoute roles={["ministry"]}>
            <AppShell><MinistryDashboard /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/state"
        element={
          <ProtectedRoute roles={["state"]}>
            <AppShell><StateDashboard /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/mp"
        element={
          <ProtectedRoute roles={["mp"]}>
            <AppShell><MPDashboard /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/district"
        element={
          <ProtectedRoute roles={["district"]}>
            <AppShell><DistrictDashboard /></AppShell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/works"
        element={
          <ProtectedRoute>
            <AppShell><WorksExplorer /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/works/:workId"
        element={
          <ProtectedRoute>
            <AppShell><ProjectDetail /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/alerts"
        element={
          <ProtectedRoute>
            <AppShell><Alerts /></AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute roles={["ministry", "state"]}>
            <AppShell><UploadData /></AppShell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/"
        element={<Navigate to={user ? ROLE_HOME[user.role] || "/works" : "/login"} replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
