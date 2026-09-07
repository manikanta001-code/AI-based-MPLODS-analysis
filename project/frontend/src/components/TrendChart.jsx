import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

function crores(v) {
  return `₹${(v / 1e7).toFixed(1)}Cr`;
}

export default function TrendChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-sm text-muted py-8 text-center">No trend data available.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#D7DBD6" vertical={false} />
        <XAxis dataKey="year" tick={{ fontSize: 12, fill: "#5B6660" }} axisLine={{ stroke: "#D7DBD6" }} tickLine={false} />
        <YAxis tickFormatter={crores} tick={{ fontSize: 12, fill: "#5B6660" }} axisLine={false} tickLine={false} width={70} />
        <Tooltip
          formatter={(v) => crores(v)}
          contentStyle={{ border: "1px solid #D7DBD6", borderRadius: 0, fontSize: 13, fontFamily: "IBM Plex Sans" }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="total_sanctioned" name="Sanctioned" stroke="#16212E" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="total_disbursed" name="Disbursed" stroke="#2B6777" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
