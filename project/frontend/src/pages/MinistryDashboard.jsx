import { useEffect, useState } from "react";
import { api } from "../api/client";
import DashboardLayout from "../components/DashboardLayout";

export default function MinistryDashboard() {
  const [bundle, setBundle] = useState(null);
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/api/roles/ministry"), api.get("/api/analytics/yearly-trends")])
      .then(([b, t]) => {
        setBundle(b);
        setTrend(t);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout
      title="Ministry Dashboard"
      subtitle="National oversight — all states, all MPs"
      loading={loading}
      error={error}
      summary={bundle?.summary}
      topAlerts={bundle?.top_alerts}
      ranking={bundle?.ranking}
      rankingLabel={bundle?.ranking_label}
      rankingKey="state"
      trend={trend}
    />
  );
}
