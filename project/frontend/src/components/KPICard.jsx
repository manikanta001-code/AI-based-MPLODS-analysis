export default function KPICard({ label, value, sublabel, accent = "accent", mono = true }) {
  const ruleColor = {
    accent: "border-t-accent",
    high: "border-t-risk-high",
    medium: "border-t-risk-medium",
    low: "border-t-risk-low",
    ink: "border-t-ink",
  }[accent];

  return (
    <div className={`bg-surface border border-line border-t-[3px] ${ruleColor} px-5 py-4`}>
      <div className="text-sm text-muted">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold text-ink ${mono ? "tabular" : ""}`}>
        {value}
      </div>
      {sublabel && <div className="mt-1 text-xs text-muted">{sublabel}</div>}
    </div>
  );
}
