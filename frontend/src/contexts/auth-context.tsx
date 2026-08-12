"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { apiErrorMessage, authApi, type RegisterInput } from "@/lib/api-client";
import { clearToken, getToken, setToken } from "@/lib/token";
import type { UserRead } from "@/lib/types";

interface AuthContextValue {
  user: UserRead | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  const loadCurrentUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount to restore a session from a persisted token: the
    // textbook case for an effect (synchronizing React state with an
    // external system - here, "is this stored token still valid").
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadCurrentUser();
  }, [loadCurrentUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await authApi.login(email, password);
      setToken(token.access_token);
      const me = await authApi.me();
      setUser(me);
    },
    [],
  );

  const register = useCallback(async (data: RegisterInput) => {
    await authApi.register(data);
    const token = await authApi.login(data.email, data.password);
    setToken(token.access_token);
    const me = await authApi.me();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export { apiErrorMessage };
