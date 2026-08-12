"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi, downloadFile } from "@/lib/api";
import { getScopeExplanation } from "@/lib/scopeLookup";
import { AuditInfoButton } from "@/components/AuditModal";
import { InsightsAndAskPanel } from "@/components/InsightsAndAskPanel";
import {
  Download,
  Building2,
  Filter,
  DollarSign,
  TrendingUp,
  CreditCard,
  Target,
  BarChart3,
  Layers,
  Users,
  MapPin,
  RefreshCw,
  Info
} from "lucide-react";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid
} from "recharts";

interface KpiData {
  scope: "org" | "category";
  gross_revenue: number | null;
  net_revenue: number | null;
  refund_amount: number | null;
  refund_percent: number | null;
  orders: number | null;
  average_selling_price: number | null;
  today_sales: number | null;
  yesterday_sales: number | null;
  daily_run_rate: number | null;
  wow_growth: number | null;
  mom_growth: number | null;
  growth_data_scope?: string;
  total_target: number | null;
  target_achieved_percent: number | null;
  target_remaining: number | null;
  required_drr: number | null;
  target_data_scope?: string;
  expected_month_revenue: number | null;
  forecast_target_achievement: number | null;
  forecast_data_scope?: string;
  profit: number | null;
  loss: number | null;
  category_performance?: any[];
  batch_performance?: any[];
  teacher_performance?: any[];
  state_performance?: any[];
}

interface DashboardResponse {
  dataset_id: string;
  filename: string;
  uploaded_at: string;
  kpi_data: KpiData;
}

export default function DashboardPage() {
  const params = useParams();
  const datasetId = params.datasetId as string;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-950 text-white flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
          <DashboardContent datasetId={datasetId} />
        </main>
      </div>
    </ProtectedRoute>
  );
}

function DashboardContent({ datasetId }: { datasetId: string }) {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("executive");

  useEffect(() => {
    if (!user?.token || !datasetId) return;
    setLoading(true);
    fetchApi<DashboardResponse>(`/dashboard/${datasetId}`, {}, user.token)
      .then((res) => setData(res))
      .catch((err) => setError(err.message || "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [datasetId, user?.token]);

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-4 text-slate-400">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent"></div>
        <p className="text-sm font-medium">Loading Dashboard metrics & scoping rules...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl max-w-md mx-auto mt-12 text-center">
        <p className="font-semibold text-base mb-2">Error Loading Dashboard</p>
        <p className="text-xs text-rose-400">{error || "Dataset not found"}</p>
      </div>
    );
  }

  const kpi = data.kpi_data;
  const isCategoryScope = kpi.scope === "category";

  return (
    <div className="space-y-6">
      {/* Header Banner with Persistent Scope Indicator */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-xl">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-white">{data.filename}</h1>
            {isCategoryScope ? (
              <span className="px-3 py-1 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5" />
                Showing: {user?.assignedCategory || "Assigned Category"} only
              </span>
            ) : (
              <span className="px-3 py-1 bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5" />
                Showing: All categories
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400">Dataset ID: {datasetId} | Uploaded: {new Date(data.uploaded_at).toLocaleString()}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => downloadFile(`/export/${datasetId}?format=xlsx`, `${data.filename}_report.xlsx`, user?.token)}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 text-xs font-semibold rounded-lg transition flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            Excel Export
          </button>
          <button
            onClick={() => downloadFile(`/export/${datasetId}?format=pdf`, `${data.filename}_report.pdf`, user?.token)}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            PDF Export
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 overflow-x-auto pb-1">
        {[
          { id: "executive", label: "Executive Summary", icon: BarChart3 },
          { id: "sales", label: "Sales & Orders", icon: DollarSign },
          { id: "target", label: "Targets & Performance", icon: Target },
          { id: "batch", label: "Batch Breakdown", icon: Layers },
          { id: "category", label: "Category Performance", icon: Filter },
          { id: "teacher", label: "Teacher Stats", icon: Users },
          { id: "state", label: "State Breakdown", icon: MapPin },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition flex items-center gap-2 whitespace-nowrap ${
                active
                  ? "bg-slate-900 border-t border-x border-slate-800 text-indigo-400 border-b-2 border-b-indigo-500"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === "executive" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Gross Revenue"
              value={kpi.gross_revenue}
              prefix="₹"
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="Net Revenue"
              value={kpi.net_revenue}
              prefix="₹"
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="Refund Amount"
              value={kpi.refund_amount}
              prefix="₹"
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="Total Profit"
              value={kpi.profit}
              prefix="₹"
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="Total Target"
              value={kpi.total_target}
              prefix="₹"
              scopeFlag={kpi.target_data_scope}
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="MoM Growth"
              value={kpi.mom_growth}
              suffix="%"
              scopeFlag={kpi.growth_data_scope}
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="WoW Growth"
              value={kpi.wow_growth}
              suffix="%"
              scopeFlag={kpi.growth_data_scope}
              datasetId={datasetId}
              token={user?.token || ""}
            />
            <MetricCard
              label="Forecasted Revenue"
              value={kpi.expected_month_revenue}
              prefix="₹"
              scopeFlag={kpi.forecast_data_scope}
              datasetId={datasetId}
              token={user?.token || ""}
            />
          </div>
        )}

        {activeTab === "sales" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard label="Total Orders" value={kpi.orders} datasetId={datasetId} token={user?.token || ""} />
            <MetricCard label="Average Selling Price" value={kpi.average_selling_price} prefix="₹" datasetId={datasetId} token={user?.token || ""} />
            <MetricCard label="Refund %" value={kpi.refund_percent} suffix="%" datasetId={datasetId} token={user?.token || ""} />
          </div>
        )}

        {activeTab === "target" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard label="Total Target" value={kpi.total_target} prefix="₹" scopeFlag={kpi.target_data_scope} datasetId={datasetId} token={user?.token || ""} />
            <MetricCard label="Target Achieved %" value={kpi.target_achieved_percent} suffix="%" scopeFlag={kpi.target_data_scope} datasetId={datasetId} token={user?.token || ""} />
            <MetricCard label="Target Remaining" value={kpi.target_remaining} prefix="₹" scopeFlag={kpi.target_data_scope} datasetId={datasetId} token={user?.token || ""} />
          </div>
        )}

        {activeTab === "batch" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-bold text-base mb-4 text-white">Batch Performance Chart</h3>
            {kpi.batch_performance && kpi.batch_performance.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={kpi.batch_performance}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="batch" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                    <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} name="Revenue (₹)" />
                    <Bar dataKey="profit" fill="#10b981" radius={[4, 4, 0, 0]} name="Profit (₹)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No batch performance data available.</p>
            )}
          </div>
        )}

        {activeTab === "category" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-bold text-base mb-4 text-white">Category Performance</h3>
            {kpi.category_performance && kpi.category_performance.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-800 text-slate-300">
                      <th className="p-3 border border-slate-700 font-semibold">Category</th>
                      <th className="p-3 border border-slate-700 font-semibold">Revenue (₹)</th>
                      <th className="p-3 border border-slate-700 font-semibold">Orders</th>
                      <th className="p-3 border border-slate-700 font-semibold">Profit (₹)</th>
                      <th className="p-3 border border-slate-700 font-semibold">Margin Used</th>
                      <th className="p-3 border border-slate-700 font-semibold">Placeholder Estimate?</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kpi.category_performance.map((c, idx) => (
                      <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/40">
                        <td className="p-3 border border-slate-800 text-white font-semibold">{c.category}</td>
                        <td className="p-3 border border-slate-800 text-indigo-300">₹{c.revenue?.toLocaleString()}</td>
                        <td className="p-3 border border-slate-800 text-slate-300">{c.orders}</td>
                        <td className="p-3 border border-slate-800 text-emerald-400">₹{c.profit?.toLocaleString()}</td>
                        <td className="p-3 border border-slate-800 text-slate-300">{(c.margin_used * 100).toFixed(0)}%</td>
                        <td className="p-3 border border-slate-800">
                          {c.is_default ? (
                            <span className="text-amber-400 font-mono">Yes (Default 45%)</span>
                          ) : (
                            <span className="text-emerald-400 font-mono">No (Verified)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No category performance data available.</p>
            )}
          </div>
        )}

        {activeTab === "teacher" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-bold text-base mb-4 text-white">Teacher Performance</h3>
            {kpi.teacher_performance && kpi.teacher_performance.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={kpi.teacher_performance}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="teacher" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                    <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Revenue (₹)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No teacher performance data available.</p>
            )}
          </div>
        )}

        {activeTab === "state" && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-bold text-base mb-4 text-white">State Revenue Breakdown</h3>
            {kpi.state_performance && kpi.state_performance.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={kpi.state_performance}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="state" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                    <Bar dataKey="revenue" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Revenue (₹)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No state breakdown data available.</p>
            )}
          </div>
        )}
      </div>

      {/* AI Insights & Grounded Q&A Panel */}
      <InsightsAndAskPanel datasetId={datasetId} token={user?.token || ""} />
    </div>
  );
}

function MetricCard({
  label,
  value,
  prefix = "",
  suffix = "",
  scopeFlag,
  datasetId,
  token,
}: {
  label: string;
  value: number | null | undefined;
  prefix?: string;
  suffix?: string;
  scopeFlag?: string;
  datasetId: string;
  token: string;
}) {
  const isScopedOut = value === null || value === undefined;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
        <span className="font-medium">{label}</span>
        <AuditInfoButton datasetId={datasetId} token={token} />
      </div>

      {isScopedOut ? (
        <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs rounded-lg flex items-center gap-2">
          <Info className="h-4 w-4 shrink-0" />
          <span className="font-medium">{getScopeExplanation(scopeFlag)}</span>
        </div>
      ) : (
        <div className="text-2xl font-bold text-white tracking-tight">
          {prefix}
          {typeof value === "number" ? value.toLocaleString() : value}
          {suffix}
        </div>
      )}
    </div>
  );
}
