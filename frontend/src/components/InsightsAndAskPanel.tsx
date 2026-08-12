"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { Sparkles, MessageSquare, AlertCircle, ShieldAlert, CheckCircle } from "lucide-react";

interface Insight {
  insight: string;
  severity: "info" | "warning" | "critical";
  supporting_kpi_ids: string[];
  recommendation: string;
  confidence: number;
  verified: boolean;
  unverified_reason?: string | null;
}

export function InsightsAndAskPanel({ datasetId, token }: { datasetId: string; token: string }) {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [insightsFetched, setInsightsFetched] = useState(false);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askResult, setAskResult] = useState<{
    answer: string;
    verified: boolean;
    unverified_reason?: string | null;
  } | null>(null);
  const [askError, setAskError] = useState("");

  const handleFetchInsights = async () => {
    setLoadingInsights(true);
    try {
      const res = await fetchApi<{ insights: Insight[] }>(
        `/insights/${datasetId}`,
        { method: "POST" },
        token
      );
      setInsights(res.insights || []);
      setInsightsFetched(true);
    } catch (err: any) {
      // ignore
    } finally {
      setLoadingInsights(false);
    }
  };

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setAskError("");
    setAskResult(null);

    try {
      const res = await fetchApi<{
        answer: string;
        verified: boolean;
        unverified_reason?: string | null;
      }>(
        `/ask/${datasetId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        },
        token
      );
      setAskResult(res);
    } catch (err: any) {
      if (err.status === 429) {
        setAskError("Daily Q&A rate limit reached (20 questions/day). Please try again tomorrow.");
      } else {
        setAskError(err.message || "Failed to process question");
      }
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
      {/* Insights Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-lg text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-indigo-400" />
              Grounded AI Executive Insights
            </h3>
            {!insightsFetched && (
              <button
                onClick={handleFetchInsights}
                disabled={loadingInsights}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-lg transition"
              >
                {loadingInsights ? "Analyzing..." : "Generate Insights"}
              </button>
            )}
          </div>

          {loadingInsights ? (
            <div className="py-12 flex flex-col items-center gap-2 text-slate-400">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></div>
              <span className="text-xs">Generating grounded insights via LLM...</span>
            </div>
          ) : insights.length > 0 ? (
            <div className="space-y-4 max-h-[400px] overflow-y-auto pr-1">
              {insights.map((ins, idx) => {
                const isVerified = ins.verified;
                const severityColors = {
                  info: "border-blue-500/30 bg-blue-500/10 text-blue-300",
                  warning: "border-amber-500/30 bg-amber-500/10 text-amber-300",
                  critical: "border-rose-500/30 bg-rose-500/10 text-rose-300",
                }[ins.severity];

                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg border text-xs space-y-2 ${
                      isVerified ? severityColors : "border-amber-500/50 bg-amber-950/20 text-amber-200"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold uppercase tracking-wider text-[10px] px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                        {ins.severity}
                      </span>
                      {isVerified ? (
                        <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-semibold">
                          <CheckCircle className="h-3.5 w-3.5" />
                          Grounded & Verified
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold px-2 py-0.5 bg-amber-500/20 rounded border border-amber-500/40">
                          <ShieldAlert className="h-3.5 w-3.5" />
                          ⚠ Unverified — treat with caution
                        </span>
                      )}
                    </div>
                    <p className="font-medium text-slate-200 text-sm">{ins.insight}</p>
                    <p className="text-slate-400">
                      <strong className="text-slate-300">Recommendation:</strong> {ins.recommendation}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-400 py-6 text-center italic">
              {insightsFetched ? "No insights returned." : "Click 'Generate Insights' to run AI analysis on this dataset."}
            </p>
          )}
        </div>
      </div>

      {/* Ask a Question Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
        <div>
          <h3 className="font-bold text-lg text-white mb-1 flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-indigo-400" />
            Ask AI Analyst (Claude)
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Ask any question regarding this dataset. Answers are grounded and rate-limited to 20 questions/day.
          </p>

          <form onSubmit={handleAsk} className="flex gap-2 mb-4">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Why did refunds spike in Coding & Tech?"
              className="flex-1 px-3.5 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={asking}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white rounded-lg transition disabled:opacity-50"
            >
              {asking ? "Thinking..." : "Ask"}
            </button>
          </form>

          {askError && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs rounded-lg flex items-center gap-2 mb-4">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{askError}</span>
            </div>
          )}

          {askResult && (
            <div className={`p-4 rounded-lg border text-xs space-y-2 ${askResult.verified ? "border-slate-800 bg-slate-950/60" : "border-amber-500/50 bg-amber-950/20"}`}>
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="font-semibold text-slate-300">Response</span>
                {askResult.verified ? (
                  <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-semibold">
                    <CheckCircle className="h-3.5 w-3.5" />
                    Verified Grounded Answer
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold px-2 py-0.5 bg-amber-500/20 rounded border border-amber-500/40">
                    <ShieldAlert className="h-3.5 w-3.5" />
                    ⚠ Unverified Answer
                  </span>
                )}
              </div>
              <p className="text-slate-200 leading-relaxed text-sm">{askResult.answer}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
