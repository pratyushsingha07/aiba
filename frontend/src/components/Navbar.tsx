"use client";

import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import { LogOut, LayoutDashboard, Upload, UserCheck } from "lucide-react";

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-3 flex items-center justify-between text-white sticky top-0 z-50">
      <div className="flex items-center gap-6">
        <Link href="/" className="font-bold text-lg text-indigo-400 flex items-center gap-2">
          <LayoutDashboard className="h-5 w-5" />
          <span>BI Dashboard SaaS</span>
        </Link>
        {user && (
          <div className="flex items-center gap-4 text-sm font-medium">
            <Link href="/upload" className="hover:text-indigo-400 flex items-center gap-1.5 transition">
              <Upload className="h-4 w-4" />
              Upload Data
            </Link>
          </div>
        )}
      </div>

      {user ? (
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2 px-3 py-1 bg-slate-800 rounded-full border border-slate-700 text-slate-300">
            <UserCheck className="h-4 w-4 text-emerald-400" />
            <span className="font-semibold text-white">{user.email}</span>
            <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-300 rounded font-mono uppercase">
              {user.role}
            </span>
          </div>
          <button
            onClick={() => logout()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 rounded-md transition text-xs font-semibold"
          >
            <LogOut className="h-3.5 w-3.5" />
            Logout
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 text-sm font-medium">
          <Link href="/login" className="hover:text-indigo-400 transition">
            Login
          </Link>
          <Link href="/signup" className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition font-semibold">
            Sign Up
          </Link>
        </div>
      )}
    </nav>
  );
}
