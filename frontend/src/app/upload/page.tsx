"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Upload, FileSpreadsheet, CheckCircle2, AlertTriangle, XCircle, ArrowRight } from "lucide-react";

interface ValidationReport {
  is_valid: boolean;
  total_rows: number;
  duplicate_order_ids: string[];
  negative_sales_count: number;
  missing_critical_fields_count: number;
  errors: Array<{
    row_index: number;
    error_type: string;
    message: string;
  }>;
  summary: Record<string, number>;
}

interface UploadResponse {
  upload_id: string;
  proposed_mapping: Record<string, Record<string, string | null>>;
  validation_report: ValidationReport;
  sheet_preview: Record<string, any[]>;
}

const SYSTEM_FIELDS: Record<string, string[]> = {
  sales: ["Date", "Sales", "OrderID", "Category", "Batch", "Teacher", "State", "Admissions"],
  refunds: ["Date", "RefundAmount", "OrderID", "Category", "Batch", "Teacher", "State"],
  targets: ["Month", "Category", "Target"],
  batches: ["Batch", "Capacity", "Teacher", "Profit"],
};

export default function UploadPage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-950 text-white flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-6xl w-full mx-auto p-6">
          <UploadFlowContent />
        </main>
      </div>
    </ProtectedRoute>
  );
}

function UploadFlowContent() {
  const { user } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState<"upload" | "mapping">("upload");
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");

  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [userMapping, setUserMapping] = useState<Record<string, Record<string, string | null>>>({});

  const handleFileUpload = async (file: File) => {
    setError("");
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Upload failed");
      }

      const data: UploadResponse = await res.json();
      setUploadData(data);
      setUserMapping(data.proposed_mapping || {});
      setStep("mapping");
    } catch (err: any) {
      setError(err.message || "Failed to upload file");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmMapping = async () => {
    if (!uploadData || !user?.token) return;
    setError("");
    setConfirming(true);

    try {
      const res = await fetchApi<{ dataset_id: string }>(
        "/confirm-mapping",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            upload_id: uploadData.upload_id,
            mapping: userMapping,
          }),
        },
        user.token
      );

      router.push(`/dashboard/${res.dataset_id}`);
    } catch (err: any) {
      if (err.status === 422 && err.detail?.validation_report) {
        setUploadData({
          ...uploadData,
          validation_report: err.detail.validation_report,
        });
        setError("Blocking validation errors encountered. Please review the report below.");
      } else {
        setError(err.message || "Failed to confirm column mapping");
      }
    } finally {
      setConfirming(false);
    }
  };

  if (step === "upload") {
    return (
      <div className="max-w-2xl mx-auto mt-12 bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl">
        <h1 className="text-2xl font-bold mb-2">Upload Business Data</h1>
        <p className="text-sm text-slate-400 mb-6">Select an Excel (.xlsx) or CSV file containing your sales, refunds, targets, or batch data.</p>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm rounded-lg flex items-center gap-2">
            <XCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
              handleFileUpload(e.dataTransfer.files[0]);
            }
          }}
          className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-10 flex flex-col items-center justify-center gap-4 transition bg-slate-950/50 cursor-pointer"
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".xlsx,.xls,.csv";
            input.onchange = (e: any) => {
              if (e.target.files && e.target.files[0]) {
                handleFileUpload(e.target.files[0]);
              }
            };
            input.click();
          }}
        >
          <div className="h-16 w-16 rounded-full bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <FileSpreadsheet className="h-8 w-8" />
          </div>
          <div className="text-center">
            <p className="text-base font-semibold text-slate-200">Drag & drop your file here, or click to browse</p>
            <p className="text-xs text-slate-500 mt-1">Supports .xlsx, .xls, and .csv (Max 50MB)</p>
          </div>
        </div>

        {loading && (
          <div className="mt-6 flex items-center justify-center gap-3 text-indigo-400">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></div>
            <span className="text-sm font-medium">Parsing file and auto-detecting column mappings...</span>
          </div>
        )}
      </div>
    );
  }

  const isBlocking = uploadData?.validation_report && (
    !uploadData.validation_report.is_valid &&
    uploadData.validation_report.missing_critical_fields_count === uploadData.validation_report.total_rows &&
    uploadData.validation_report.total_rows > 0
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Review & Confirm Column Mapping</h1>
          <p className="text-sm text-slate-400">Verify system field mappings and validation metrics before confirming dataset creation.</p>
        </div>
        <button
          onClick={handleConfirmMapping}
          disabled={confirming || isBlocking}
          className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg transition flex items-center gap-2"
        >
          {confirming ? "Confirming..." : "Confirm & Save Dataset"}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm rounded-lg flex items-center gap-2">
          <XCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Validation Report Banner */}
      {uploadData?.validation_report && (
        <div className={`p-5 rounded-xl border ${uploadData.validation_report.is_valid ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {uploadData.validation_report.is_valid ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-400" />
              )}
              <h3 className="font-semibold text-base">
                {uploadData.validation_report.is_valid ? "Validation Clean" : "Validation Warnings & Issues"}
              </h3>
            </div>
            <span className="text-xs px-2.5 py-1 bg-slate-800 rounded-full text-slate-300 font-mono">
              Total Rows: {uploadData.validation_report.total_rows}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4 mt-3 text-xs">
            <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800">
              <span className="text-slate-400">Duplicates Order IDs:</span>{" "}
              <span className="font-bold text-amber-400">{uploadData.validation_report.duplicate_order_ids?.length || 0}</span>
            </div>
            <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800">
              <span className="text-slate-400">Negative Sales Rows:</span>{" "}
              <span className="font-bold text-amber-400">{uploadData.validation_report.negative_sales_count || 0}</span>
            </div>
            <div className="p-2.5 bg-slate-900/60 rounded border border-slate-800">
              <span className="text-slate-400">Missing Critical Fields:</span>{" "}
              <span className="font-bold text-rose-400">{uploadData.validation_report.missing_critical_fields_count || 0}</span>
            </div>
          </div>
        </div>
      )}

      {/* Column Mapping Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Column Mapping Config per Sheet</h2>
        <div className="space-y-6">
          {Object.entries(SYSTEM_FIELDS).map(([sheetType, expectedFields]) => {
            const previewRows = uploadData?.sheet_preview?.[sheetType] || [];
            const availableHeaders = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];

            return (
              <div key={sheetType} className="border border-slate-800 rounded-lg p-4 bg-slate-950/40">
                <h3 className="text-sm font-bold uppercase text-indigo-400 mb-3 tracking-wider">{sheetType} Sheet Mapping</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {expectedFields.map((field) => {
                    const currentMapped = userMapping[sheetType]?.[field] || "";
                    return (
                      <div key={field} className="space-y-1">
                        <label className="text-xs text-slate-400 font-medium">{field}</label>
                        <select
                          value={currentMapped}
                          onChange={(e) => {
                            const val = e.target.value || null;
                            setUserMapping({
                              ...userMapping,
                              [sheetType]: {
                                ...(userMapping[sheetType] || {}),
                                [field]: val,
                              },
                            });
                          }}
                          className="w-full text-xs bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-indigo-500"
                        >
                          <option value="">-- Unmapped --</option>
                          {availableHeaders.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sheet Preview Table */}
      {uploadData?.sheet_preview?.sales && uploadData.sheet_preview.sales.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-3">Sales Sheet Preview (First 10 Rows)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-800 text-slate-300">
                  {Object.keys(uploadData.sheet_preview.sales[0]).map((h) => (
                    <th key={h} className="p-2 border border-slate-700 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {uploadData.sheet_preview.sales.map((row, idx) => (
                  <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/40">
                    {Object.values(row).map((val: any, vIdx) => (
                      <td key={vIdx} className="p-2 border border-slate-800 text-slate-300">
                        {val === null ? <span className="text-slate-600 font-mono">null</span> : String(val)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
