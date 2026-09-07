import { useCallback, useState } from "react";
import { UploadCloud, FileSpreadsheet } from "lucide-react";
import { api } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import { formatCrore } from "../components/RiskTable";
import { Loading, ErrorState } from "../components/Status";

export default function UploadData() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFile = useCallback((f) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
  }, []);

  async function handleScore() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.postForm("/api/upload", formData);
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="font-display text-2xl text-ink">Upload Data</h1>
        <p className="text-sm text-muted mt-1">
          Upload newly recommended works (same columns as Works_Sanctioned.csv) and get instant ML risk scores —
          no retraining, using the models trained in Phase 2.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        className={`border-2 border-dashed px-8 py-14 text-center transition-colors ${
          dragging ? "border-accent bg-accent-light/30" : "border-line bg-surface"
        }`}
      >
        <UploadCloud className="mx-auto text-muted mb-3" size={32} strokeWidth={1.5} />
        <p className="text-sm text-ink">
          Drag a CSV or Excel file here, or{" "}
          <label className="text-accent hover:underline cursor-pointer">
            browse
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </label>
        </p>
        {file && (
          <div className="mt-4 inline-flex items-center gap-2 text-sm text-ink bg-paper px-3 py-1.5">
            <FileSpreadsheet size={14} />
            {file.name}
          </div>
        )}
      </div>

      <button
        onClick={handleScore}
        disabled={!file || loading}
        className="bg-accent text-white text-sm font-medium px-5 py-2.5 hover:bg-accent-dark disabled:opacity-40 transition-colors"
      >
        {loading ? "Scoring…" : "Score with AI models"}
      </button>

      {loading && <Loading label="Cleaning, engineering features, and scoring…" />}
      {error && <ErrorState message={error} />}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="border border-line border-t-[3px] border-t-risk-high bg-surface px-4 py-3">
              <div className="text-xs text-muted">High risk</div>
              <div className="text-xl font-semibold tabular">{result.high_risk_count}</div>
            </div>
            <div className="border border-line border-t-[3px] border-t-risk-medium bg-surface px-4 py-3">
              <div className="text-xs text-muted">Medium risk</div>
              <div className="text-xl font-semibold tabular">{result.medium_risk_count}</div>
            </div>
            <div className="border border-line border-t-[3px] border-t-risk-low bg-surface px-4 py-3">
              <div className="text-xs text-muted">Low risk</div>
              <div className="text-xl font-semibold tabular">{result.low_risk_count}</div>
            </div>
          </div>
          {result.rows_dropped_during_cleaning > 0 && (
            <p className="text-xs text-muted">
              {result.rows_dropped_during_cleaning} row(s) dropped during cleaning (missing Work ID or invalid
              sanction amount).
            </p>
          )}

          <div className="border border-line bg-surface divide-y divide-line">
            {result.results.map((r) => (
              <div key={r.work_id} className="px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs text-muted tabular">{r.work_id} · {r.state}</div>
                    <div className="text-sm text-ink truncate">{r.work_description}</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs tabular text-muted">{formatCrore(r.sanction_amount)}</span>
                    <span className="text-sm font-medium tabular">{r.risk_score.toFixed(1)}</span>
                    <RiskBadge band={r.risk_band} size="sm" />
                  </div>
                </div>
                <ul className="mt-2 space-y-1">
                  {r.reasons.map((reason, i) => (
                    <li key={i} className="text-xs text-muted flex gap-1.5">
                      <span className="text-accent">—</span>
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
