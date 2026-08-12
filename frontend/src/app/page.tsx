import Navbar from "@/components/Navbar";
import Link from "next/link";
import { Upload, LayoutDashboard, ShieldCheck, Sparkles, FileSpreadsheet } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-16 flex flex-col items-center justify-center text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-6">
          <Sparkles className="h-4 w-4" />
          <span>Enterprise Multi-Tenant Business Intelligence SaaS</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6 bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
          AI-Powered Business Intelligence & Execution Platform
        </h1>

        <p className="text-base md:text-lg text-slate-400 max-w-2xl mb-10 leading-relaxed">
          Upload financial sales data, run automated column mapping and strict validation, inspect real-time KPI metrics, and generate grounded AI insights with zero hallucinated calculations.
        </p>

        <div className="flex items-center gap-4">
          <Link
            href="/upload"
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition flex items-center gap-2 text-sm shadow-lg shadow-indigo-600/20"
          >
            <Upload className="h-4 w-4" />
            Upload Dataset
          </Link>
          <Link
            href="/login"
            className="px-6 py-3 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 font-semibold rounded-xl transition text-sm"
          >
            Sign In
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 text-left w-full">
          <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-xl space-y-2">
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-3">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-base text-white">Smart Excel/CSV Ingestion</h3>
            <p className="text-xs text-slate-400">Automatic column alias matching, validation error checks, and 10-row preview table before confirmation.</p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-xl space-y-2">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-base text-white">Row Level Security & Scoping</h3>
            <p className="text-xs text-slate-400">Postgres RLS boundaries per organization, plus role-based category recomputation for Category Managers.</p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-xl space-y-2">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center mb-3">
              <Sparkles className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-base text-white">Grounded AI Reasoning</h3>
            <p className="text-xs text-slate-400">Groq & Claude models reason strictly over pre-computed KPI JSON. Grounding validator flags any number mismatch.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
