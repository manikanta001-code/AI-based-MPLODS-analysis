import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

export default function UtilizationDonut({ disbursed, sanctioned }) {
  const remaining = Math.max(sanctioned - disbursed, 0);
  const data = [
    { name: "Disbursed", value: disbursed },
    { name: "Remaining sanctioned", value: remaining },
  ];
  const pct = sanctioned ? ((disbursed / sanctioned) * 100).toFixed(1) : "0.0";

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={65}
            outerRadius={90}
            startAngle={90}
            endAngle={-270}
            stroke="none"
          >
            <Cell fill="#2B6777" />
            <Cell fill="#D7DBD6" />
          </Pie>
          <Tooltip
            formatter={(v) => `₹${(v / 1e7).toFixed(2)} Cr`}
            contentStyle={{ border: "1px solid #D7DBD6", borderRadius: 0, fontSize: 13, fontFamily: "IBM Plex Sans" }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className="text-2xl font-semibold text-ink tabular">{pct}%</div>
        <div className="text-xs text-muted">utilized</div>
      </div>
    </div>
  );
}
