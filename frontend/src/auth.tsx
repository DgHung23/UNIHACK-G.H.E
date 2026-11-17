/* eslint-disable @typescript-eslint/no-explicit-any */
import { createContext, useContext, useState, type ReactNode } from "react";
import { api, getStoredUser, getToken, setSession } from "./api/client";

type Ctx = { user: any | null; login: (u: string, p: string) => Promise<void>; logout: () => void };
const AuthCtx = createContext<Ctx>({ user: null, login: async () => {}, logout: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any | null>(getToken() ? getStoredUser() : null);
  const login = async (username: string, password: string) => {
    const r = await api("/auth/login", { body: { username, password }, auth: false });
    setSession(r.token, r.user);
    setUser(r.user);
  };
  const logout = () => { setSession(null); setUser(null); };
  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
