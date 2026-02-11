import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { AuthUser } from "../types";
import { loginAPI, logoutAPI, fetchMe, refreshToken } from "../api";

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem("cronbox_token"));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const stored = localStorage.getItem("cronbox_token");
      if (!stored) {
        setIsLoading(false);
        return;
      }
      try {
        const me = await fetchMe(stored);
        if (!cancelled) {
          setUser(me);
          setToken(stored);
        }
      } catch {
        try {
          const data = await refreshToken();
          if (!cancelled) {
            localStorage.setItem("cronbox_token", data.access_token);
            setToken(data.access_token);
            setUser(data.user);
          }
        } catch {
          if (!cancelled) {
            localStorage.removeItem("cronbox_token");
            setToken(null);
            setUser(null);
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    init();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await loginAPI(username, password);
    localStorage.setItem("cronbox_token", data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAPI();
    } catch {
      // ignore logout errors
    }
    localStorage.removeItem("cronbox_token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
