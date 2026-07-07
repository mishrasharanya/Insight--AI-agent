import { useEffect, useState, useCallback } from "react";
import api, { INSIGHT_API_URL } from "./api";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data?.logged_in ? { email: data.email } : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = () => { window.location.href = `${INSIGHT_API_URL}/auth/google/login`; };
  const logout = async () => {
    try { await api.post("/auth/logout", {}); } finally {
      setUser(null);
      window.location.href = "/";
    }
  };

  return { user, loading, login, logout, refresh };
}