import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-key";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export interface UserSessionInfo {
  userId: string;
  email: string;
  orgId: string;
  role: "admin" | "business_head" | "category_manager" | "analyst";
  assignedCategory: string | null;
  token: string;
}

export function parseJwtClaims(token: string): Partial<UserSessionInfo> {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(jsonPayload);
    const appMeta = payload.app_metadata || {};
    return {
      userId: payload.sub,
      email: payload.email,
      orgId: appMeta.org_id,
      role: appMeta.role || "analyst",
      assignedCategory: appMeta.assigned_category || null,
      token,
    };
  } catch (e) {
    return { token };
  }
}
