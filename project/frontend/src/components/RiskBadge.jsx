const STYLES = {
  High: "bg-risk-highBg text-risk-high border-risk-high/30",
  Medium: "bg-risk-mediumBg text-risk-medium border-risk-medium/30",
  Low: "bg-risk-lowBg text-risk-low border-risk-low/30",
};

export default function RiskBadge({ band, size = "md" }) {
  const cls = STYLES[band] || "bg-line/40 text-muted border-line";
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border font-medium ${pad} ${cls}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {band}
    </span>
  );
}
