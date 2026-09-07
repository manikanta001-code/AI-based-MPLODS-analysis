import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import { formatCrore } from "../components/RiskTable";
import { Loading, ErrorState } from "../components/Status";

function Field({ label, value }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="text-sm text-ink mt-0.5">{value ?? "—"}</div>
    </div>
  );
}

function ScoreBar({ label, value, tone }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-muted mb-1">
        <span>{label}</span>
        <span className="tabular font-medium text-ink">{value?.toFixed(1)}</span>
      </div>
      <div className="h-2 bg-paper">
        <div className={`h-2 ${tone}`} style={{ width: `${Math.min(value || 0, 100)}%` }} />
      </div>
    </div>
  );
}

export default function ProjectDetail() {
  const { workId } = useParams();
  const [work, setWork] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get(`/api/works/${workId}`)
      .then(setWork)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [workId]);

  if (loading) return <Loading label="Loading work detail…" />;
  if (error) return <ErrorState message={error} />;
  if (!work) return null;

  const reasons = (work.risk_reasons || "").split("; ").filter(Boolean);

  return (
    <div className="space-y-6 max-w-4xl">
      <Link to="/works" className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline">
        <ArrowLeft size={14} /> Back to Works
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-muted tabular">{work.work_id}</div>
          <h1 className="font-display text-2xl text-ink mt-1 leading-snug">{work.work_description}</h1>
        </div>
        <div className="text-right shrink-0">
          <div className="text-3xl font-semibold tabular text-ink">{work.risk_score.toFixed(1)}</div>
          <RiskBadge band={work.risk_band} />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 border border-line bg-surface p-5">
        <Field label="State" value={work.state} />
        <Field label="MP" value={work.mp_name} />
        <Field label="Constituency" value={work.constituency} />
        <Field label="Category" value={work.work_category} />
        <Field label="Implementing Agency" value={work.ida} />
        <Field label="Status" value={work.work_status} />
        <Field label="Sanction amount" value={formatCrore(work.sanction_amount)} />
        <Field label="Amount disbursed" value={work.amount_disbursed ? formatCrore(work.amount_disbursed) : "—"} />
        <Field label="Recommended" value={work.recommended_date} />
        <Field label="Sanctioned" value={work.sanction_date} />
        <Field label="Completed" value={work.completion_date || "In progress"} />
        <Field label="Utilization" value={work.utilization_pct >= 0 ? `${work.utilization_pct.toFixed(0)}%` : "—"} />
      </div>

      <section className="border border-line bg-surface p-5">
        <h2 className="font-display text-lg text-ink mb-4">AI risk breakdown</h2>
        <div className="grid md:grid-cols-2 gap-x-8 gap-y-4">
          <ScoreBar label="Anomaly score" value={work.anomaly_score} tone="bg-risk-high" />
          <ScoreBar label="Delay risk" value={work.delay_risk_pct} tone="bg-risk-medium" />
          <ScoreBar label="Cost risk" value={work.cost_risk_pct} tone="bg-accent" />
          <ScoreBar label="Duplicate score" value={work.duplicate_score} tone="bg-ink" />
        </div>
      </section>

      <section className="border border-line bg-surface p-5">
        <h2 className="font-display text-lg text-ink mb-3">Why this work was flagged</h2>
        {reasons.length > 0 ? (
          <ul className="space-y-2">
            {reasons.map((r, i) => (
              <li key={i} className="text-sm text-ink flex gap-2">
                <span className="text-accent">—</span>
                {r}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No significant risk factors detected.</p>
        )}
        {work.duplicate_match_work_id && (
          <p className="text-sm text-muted mt-3">
            Nearest matching work:{" "}
            <Link to={`/works/${work.duplicate_match_work_id}`} className="text-accent hover:underline tabular">
              {work.duplicate_match_work_id}
            </Link>
          </p>
        )}
      </section>
    </div>
  );
}
