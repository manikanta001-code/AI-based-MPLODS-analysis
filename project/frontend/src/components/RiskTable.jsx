import { Link } from "react-router-dom";
import RiskBadge from "./RiskBadge";

function formatCrore(amount) {
  if (amount === null || amount === undefined) return "—";
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return `₹${Number(amount).toLocaleString("en-IN")}`;
}

export default function RiskTable({ rows, showState = true, showMp = true, dense = false }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="border border-line bg-surface px-6 py-10 text-center text-sm text-muted">
        No works match the current filters.
      </div>
    );
  }

  const pad = dense ? "py-2" : "py-3";

  return (
    <div className="border border-line bg-surface overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-4 py-2.5 font-medium">Work</th>
            {showState && <th className="px-4 py-2.5 font-medium">State</th>}
            {showMp && <th className="px-4 py-2.5 font-medium">MP</th>}
            <th className="px-4 py-2.5 font-medium">Category</th>
            <th className="px-4 py-2.5 font-medium text-right">Amount</th>
            <th className="px-4 py-2.5 font-medium text-right">Risk score</th>
            <th className="px-4 py-2.5 font-medium">Band</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.work_id} className="border-b border-line last:border-0 hover:bg-paper/60">
              <td className={`px-4 ${pad}`}>
                <Link to={`/works/${r.work_id}`} className="text-accent hover:underline tabular text-xs">
                  {r.work_id}
                </Link>
                <div className="text-xs text-muted truncate max-w-xs">{r.work_description}</div>
              </td>
              {showState && <td className={`px-4 ${pad} text-xs`}>{r.state}</td>}
              {showMp && <td className={`px-4 ${pad} text-xs`}>{r.mp_name}</td>}
              <td className={`px-4 ${pad} text-xs`}>{r.work_category}</td>
              <td className={`px-4 ${pad} text-right tabular text-xs`}>{formatCrore(r.sanction_amount)}</td>
              <td className={`px-4 ${pad} text-right tabular text-xs font-medium`}>
                {r.risk_score?.toFixed(1)}
              </td>
              <td className={`px-4 ${pad}`}>
                <RiskBadge band={r.risk_band} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { formatCrore };
