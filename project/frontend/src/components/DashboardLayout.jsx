import { Link } from "react-router-dom";
import KPICard from "./KPICard";
import RiskTable from "./RiskTable";
import RankingChart from "./RankingChart";
import TrendChart from "./TrendChart";
import { Loading, ErrorState } from "./Status";

function pct(v) {
  return v === null || v === undefined ? "—" : `${v.toFixed(1)}%`;
}
function crore(v) {
  if (v === null || v === undefined) return "—";
  return `₹${(v / 1e7).toFixed(2)} Cr`;
}

export default function DashboardLayout({
  title,
  subtitle,
  loading,
  error,
  summary,
  topAlerts,
  ranking,
  rankingLabel,
  rankingKey,
  rankingValueKey = "flagged_high_count",
  trend,
  showState = true,
  showMp = true,
}) {
  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} />;
  if (!summary) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1">{subtitle}</p>}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard label="Total works" value={summary.total_works?.toLocaleString("en-IN")} accent="ink" />
        <KPICard label="Sanctioned amount" value={crore(summary.total_sanctioned_amount)} accent="accent" />
        <KPICard
          label="Fund utilization"
          value={pct(summary.utilization_pct)}
          sublabel={crore(summary.total_disbursed_amount) + " disbursed"}
          accent="accent"
        />
        <KPICard label="High-risk flagged" value={summary.flagged_high?.toLocaleString("en-IN")} accent="high" />
        <KPICard label="Completed works" value={summary.completed_works?.toLocaleString("en-IN")} accent="low" />
        <KPICard label="Ongoing works" value={(summary.total_works - summary.completed_works)?.toLocaleString("en-IN")} accent="ink" />
        <KPICard label="Predicted delayed" value={summary.predicted_delayed_count?.toLocaleString("en-IN")} accent="medium" />
        <KPICard label="Avg. risk score" value={summary.avg_risk_score?.toFixed(1)} accent="ink" />
      </div>

      {trend && (
        <section>
          <h2 className="font-display text-lg text-ink mb-3">Sanctioned vs. disbursed, by year</h2>
          <div className="border border-line bg-surface p-4">
            <TrendChart data={trend} />
          </div>
        </section>
      )}

      {ranking && (
        <section>
          <h2 className="font-display text-lg text-ink mb-3">{rankingLabel}</h2>
          <div className="border border-line bg-surface p-4">
            <RankingChart data={ranking} labelKey={rankingKey} valueKey={rankingValueKey} />
          </div>
        </section>
      )}

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-lg text-ink">Top risk alerts</h2>
          <Link to="/alerts" className="text-sm text-accent hover:underline">
            View all alerts →
          </Link>
        </div>
        <RiskTable rows={topAlerts} showState={showState} showMp={showMp} dense />
      </section>
    </div>
  );
}
