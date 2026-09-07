import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import RiskBadge from "../components/RiskBadge";
import Filters from "../components/Filters";
import { Loading, ErrorState } from "../components/Status";
import { formatCrore } from "../components/RiskTable";

function BadgeChip({ label, value, tone }) {
  return (
    <div className={`px-2 py-1 border text-xs ${tone} flex items-center gap-1.5`}>
      <span className="text-muted">{label}</span>
      <span className="font-medium tabular">{value?.toFixed(0)}</span>
    </div>
  );
}

export default function Alerts() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({ risk_band: "High" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api
      .get("/api/alerts", { ...filters, page, page_size: 20 })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters, page]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl text-ink">Risk Alerts</h1>
        <p className="text-sm text-muted mt-1">
          Every reason shown here traces back to a trained ML model's output — not a hand-written rule.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Filters
          value={filters}
          onChange={(v) => {
            setFilters(v);
            setPage(1);
          }}
          showState={user?.role === "ministry"}
          showDistrict={user?.role === "ministry" || user?.role === "state"}
        />
      </div>

      {loading && <Loading label="Loading alerts…" />}
      {error && <ErrorState message={error} />}

      {data && (
        <>
          <div className="border border-line bg-surface divide-y divide-line">
            {data.alerts.length === 0 && (
              <div className="px-6 py-10 text-center text-sm text-muted">No alerts match the current filters.</div>
            )}
            {data.alerts.map((a) => {
              const isOpen = expanded === a.work_id;
              return (
                <div key={a.work_id}>
                  <button
                    onClick={() => setExpanded(isOpen ? null : a.work_id)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-paper/60"
                  >
                    {isOpen ? <ChevronDown size={15} className="text-muted shrink-0" /> : <ChevronRight size={15} className="text-muted shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/works/${a.work_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-accent hover:underline tabular text-xs"
                        >
                          {a.work_id}
                        </Link>
                        <span className="text-xs text-muted">{a.state} · {a.mp_name}</span>
                      </div>
                      <div className="text-sm text-ink truncate">{a.work_description}</div>
                    </div>
                    <div className="text-xs tabular text-muted shrink-0">{formatCrore(a.sanction_amount)}</div>
                    <div className="text-sm font-medium tabular w-12 text-right shrink-0">{a.risk_score.toFixed(1)}</div>
                    <RiskBadge band={a.risk_band} size="sm" />
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 pl-11 space-y-3 bg-paper/40">
                      <div className="flex flex-wrap gap-2">
                        <BadgeChip label="Anomaly" value={a.badges.anomaly_score} tone="border-line" />
                        <BadgeChip label="Delay risk" value={a.badges.delay_risk_pct} tone="border-line" />
                        <BadgeChip label="Cost risk" value={a.badges.cost_risk_pct} tone="border-line" />
                        <BadgeChip label="Duplicate" value={a.badges.duplicate_score} tone="border-line" />
                      </div>
                      <ul className="space-y-1">
                        {a.reasons.map((r, i) => (
                          <li key={i} className="text-sm text-ink flex gap-2">
                            <span className="text-accent">—</span>
                            {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              Page {data.page} of {data.total_pages} · {data.total.toLocaleString("en-IN")} total
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 border border-line disabled:opacity-40 hover:border-accent"
              >
                Previous
              </button>
              <button
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 border border-line disabled:opacity-40 hover:border-accent"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
