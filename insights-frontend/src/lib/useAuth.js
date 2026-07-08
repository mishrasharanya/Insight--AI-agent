import { useEffect, useState, useCallback } from "react";
import api, { INSIGHT_API_URL } from "./api";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      localStorage.setItem("insight_token", urlToken);
      params.delete("token");
      const clean = window.location.pathname + (params.toString() ? `?${params}` : "");
      window.history.replaceState({}, "", clean);
    }

    try {
      const { data } = await api.get("/auth/me");
      setUser(data.logged_in ? { email: data.email } : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = () => {
    window.location.href = `${INSIGHT_API_URL}/auth/google/login`;
  };

  const logout = async () => {
    localStorage.removeItem("insight_token");
    localStorage.removeItem("insight_chat");
    try { await api.post("/auth/logout"); } catch {}
    setUser(null);
    window.location.href = "/";
  };

  return { user, loading, login, logout };
}