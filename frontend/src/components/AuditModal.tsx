"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Info, X } from "lucide-react";

interface AuditEntry {
  audit_id: string;
  action: string;
  performed_by: string;
  timestamp: string;
  column_mapping_used: Record<string, any>;
  validation_warnings: any[];
  default_margins_applied: Record<string, any>;
  validation_summary: Record<string, any>;
}

interface AuditResponse {
  dataset_id: string;
  filename: string;
  audit_log: AuditEntry[];
}

export function AuditInfoButton({ datasetId, token }: { datasetId: string; token: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [auditData, setAuditData] = useState<AuditResponse | null>(null);

  const handleOpen = async () => {
    setOpen(true);
    if (!auditData) {
      setLoading(true);
      try {
        const res = await fetchApi<AuditResponse>(`/audit/${datasetId}`, {}, token);
        setAuditData(res);
      } catch (err) {
        // ignore
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <>
      <button
        onClick={handleOpen}
        className="p-1 text-slate-400 hover:text-indigo-400 rounded transition"
        title="View Audit Trail for this KPI"
      >
        <Info className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-xl w-full p-6 text-white space-y-4 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-base flex items-center gap-2">
                <Info className="h-4 w-4 text-indigo-400" />
                KPI Audit Trail & Provenance
              </h3>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            {loading ? (
              <div className="py-8 flex justify-center text-slate-400 text-sm">
                Loading audit trail...
              </div>
            ) : auditData && auditData.audit_log.length > 0 ? (
              <div className="space-y-4 text-xs">
                {auditData.audit_log.map((entry) => (
                  <div key={entry.audit_id} className="bg-slate-950/60 p-4 rounded-lg border border-slate-800 space-y-3">
                    <div className="flex justify-between font-mono text-slate-400 text-[11px]">
                      <span>Action: {entry.action}</span>
                      <span>{new Date(entry.timestamp).toLocaleString()}</span>
                    </div>

                    <div>
                      <h4 className="font-semibold text-indigo-300 mb-1">Column Mapping Used:</h4>
                      <pre className="bg-slate-900 p-2 rounded text-[11px] overflow-x-auto text-slate-300 font-mono">
                        {JSON.stringify(entry.column_mapping_used, null, 2)}
                      </pre>
                    </div>

                    <div>
                      <h4 className="font-semibold text-indigo-300 mb-1">Category Margins & Placeholder Status:</h4>
                      {Object.keys(entry.default_margins_applied || {}).length > 0 ? (
                        <ul className="list-disc pl-4 space-y-0.5 text-slate-300">
                          {Object.entries(entry.default_margins_applied).map(([cat, info]: [string, any]) => (
                            <li key={cat}>
                              <span className="font-semibold">{cat}:</span> Margin {info.margin * 100}%{" "}
                              {info.is_default ? (
                                <span className="text-amber-400 font-mono">(Placeholder Estimate)</span>
                              ) : (
                                <span className="text-emerald-400 font-mono">(Verified Figure)</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-slate-400 italic">No default margin estimates used.</p>
                      )}
                    </div>

                    <div>
                      <h4 className="font-semibold text-indigo-300 mb-1">Validation Summary:</h4>
                      <pre className="bg-slate-900 p-2 rounded text-[11px] text-slate-300 font-mono">
                        {JSON.stringify(entry.validation_summary, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-slate-400 text-sm">No audit trail entries found.</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
