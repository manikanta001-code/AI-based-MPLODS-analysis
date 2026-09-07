import { useEffect, useState } from "react";
import { api } from "../api/client";
import DashboardLayout from "../components/DashboardLayout";
import { Loading, ErrorState } from "../components/Status";

const STATUS_COLORS = {
  "Work Completed": "bg-risk-low",
  "Work partially Completed": "bg-accent",
  "Physical Inspection": "bg-risk-medium",
  "Vendor Identification": "bg-ink/60",
  "Sanction": "bg-ink/40",
  "Time Estimation": "bg-ink/30",
};

export default function DistrictDashboard() {
  const [bundle, setBundle] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusCounts, setStatusCounts] = useState(null);

  useEffect(() => {
    api
      .get("/api/roles/district")
      .then(async (b) => {
        setBundle(b);
        if (b?.scope?.ida) {
          const statuses = ["Work Completed", "Work partially Completed", "Physical Inspection", "Vendor Identification", "Sanction", "Time Estimation"];
          const counts = await Promise.all(
            statuses.map((s) =>
              api.get("/api/works", { ida: b.scope.ida, work_status: s, page_size: 1 }).then((r) => ({ status: s, count: r.total }))
            )
          );
          setStatusCounts(counts.filter((c) => c.count > 0));
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} />;

  const maxCount = statusCounts ? Math.max(...statusCounts.map((c) => c.count)) : 1;

  return (
    <div className="space-y-8">
      <div className="grid md:grid-cols-3 gap-8 items-start">
        <div className="md:col-span-2">
          <DashboardLayout
            title="District Dashboard"
            subtitle={bundle?.scope?.ida ? `Agency: ${bundle.scope.ida.split("(")[0]}` : undefined}
            loading={false}
            error={null}
            summary={bundle?.summary}
            topAlerts={bundle?.top_alerts}
            ranking={bundle?.ranking}
            rankingLabel={bundle?.ranking_label}
            rankingKey="work_category"
            rankingValueKey="total_sanctioned"
            showState={false}
          />
        </div>
        <div className="border border-line bg-surface p-5">
          <h2 className="font-display text-lg text-ink mb-3">Execution status breakdown</h2>
          {statusCounts ? (
            <div className="space-y-2.5">
              {statusCounts.map((c) => (
                <div key={c.status}>
                  <div className="flex justify-between text-xs text-muted mb-1">
                    <span>{c.status}</span>
                    <span className="tabular">{c.count}</span>
                  </div>
                  <div className="h-2 bg-paper">
                    <div
                      className={`h-2 ${STATUS_COLORS[c.status] || "bg-ink/40"}`}
                      style={{ width: `${(c.count / maxCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted">Loading…</div>
          )}
        </div>
      </div>
    </div>
  );
}
