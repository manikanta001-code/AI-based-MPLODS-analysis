import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

function formatValue(v, key) {
  if (key === "total_sanctioned" || key === "total_disbursed") return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (key === "avg_risk_score") return v?.toFixed(1);
  return v;
}

export default function RankingChart({ data, labelKey, valueKey = "flagged_high_count", height = 300 }) {
  if (!data || data.length === 0) {
    return <div className="text-sm text-muted py-8 text-center">No ranking data available.</div>;
  }

  const chartData = [...data]
    .sort((a, b) => (b[valueKey] || 0) - (a[valueKey] || 0))
    .slice(0, 10)
    .reverse()
    .map((d) => ({ ...d, _label: (d[labelKey] || "Unknown").split("(")[0].trim() }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
        <CartesianGrid stroke="#D7DBD6" horizontal={false} />
        <XAxis type="number" tickFormatter={(v) => formatValue(v, valueKey)} tick={{ fontSize: 11, fill: "#5B6660" }} axisLine={{ stroke: "#D7DBD6" }} tickLine={false} />
        <YAxis
          type="category"
          dataKey="_label"
          width={140}
          tick={{ fontSize: 12, fill: "#16212E" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(v) => formatValue(v, valueKey)}
          contentStyle={{ border: "1px solid #D7DBD6", borderRadius: 0, fontSize: 13, fontFamily: "IBM Plex Sans" }}
        />
        <Bar dataKey={valueKey} radius={[0, 2, 2, 0]}>
          {chartData.map((_, i) => (
            <Cell key={i} fill="#A8342A" fillOpacity={0.55 + (0.45 * i) / chartData.length} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
