"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { parseJwtClaims, supabase, UserSessionInfo } from "@/lib/supabase";

interface AuthContextType {
  user: UserSessionInfo | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  signup: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        const parsed = parseJwtClaims(session.access_token);
        setUser({
          userId: session.user.id,
          email: session.user.email || "",
          orgId: parsed.orgId || "00000000-0000-0000-0000-000000000000",
          role: (parsed.role as any) || "analyst",
          assignedCategory: parsed.assignedCategory || null,
          token: session.access_token,
        });
      } else {
        setUser(null);
      }
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        const parsed = parseJwtClaims(session.access_token);
        setUser({
          userId: session.user.id,
          email: session.user.email || "",
          orgId: parsed.orgId || "00000000-0000-0000-0000-000000000000",
          role: (parsed.role as any) || "analyst",
          assignedCategory: parsed.assignedCategory || null,
          token: session.access_token,
        });
      } else {
        setUser(null);
      }
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const login = async (email: string, pass: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password: pass });
    if (error) throw error;
  };

  const loginWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({ provider: "google" });
    if (error) throw error;
  };

  const signup = async (email: string, pass: string) => {
    const { error } = await supabase.auth.signUp({ email, password: pass });
    if (error) throw error;
  };

  const logout = async () => {
    await supabase.auth.signOut();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, loginWithGoogle, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
