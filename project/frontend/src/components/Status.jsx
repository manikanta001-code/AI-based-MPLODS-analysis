export function Loading({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted py-10 justify-center">
      <span className="h-3 w-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="border border-risk-high/30 bg-risk-highBg text-risk-high text-sm px-4 py-3">
      {message || "Something went wrong loading this data."}
    </div>
  );
}
