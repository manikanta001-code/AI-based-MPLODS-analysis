import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) {
    const fallback = { ministry: "/ministry", state: "/state", mp: "/mp", district: "/district" }[user.role] || "/works";
    return <Navigate to={fallback} replace />;
  }
  return children;
}
