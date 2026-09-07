import { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin, setToken, getToken } from "../api/client";

const AuthContext = createContext(null);

function decodeJwt(token) {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

function userFromToken(token) {
  const payload = decodeJwt(token);
  if (!payload) return null;
  return { username: payload.sub, role: payload.role, scope: payload.scope };
}

export function AuthProvider({ children }) {
  const existingToken = getToken();
  const [user, setUser] = useState(existingToken ? userFromToken(existingToken) : null);
  const [displayName, setDisplayName] = useState(null);

  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password);
    setToken(data.access_token);
    setUser({ username, role: data.role, scope: data.scope });
    setDisplayName(data.display_name);
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setDisplayName(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, displayName, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
