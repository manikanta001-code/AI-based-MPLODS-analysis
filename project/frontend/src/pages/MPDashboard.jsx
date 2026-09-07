import { useEffect, useState } from "react";
import { api } from "../api/client";
import DashboardLayout from "../components/DashboardLayout";
import UtilizationDonut from "../components/UtilizationDonut";
import { Loading, ErrorState } from "../components/Status";

export default function MPDashboard() {
  const [bundle, setBundle] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/api/roles/mp")
      .then(setBundle)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-8">
      <div className="grid md:grid-cols-3 gap-8 items-start">
        <div className="md:col-span-2">
          <DashboardLayout
            title="MP Dashboard"
            subtitle={bundle?.scope?.mp_name ? `Own works — ${bundle.scope.mp_name}` : undefined}
            loading={false}
            error={null}
            summary={bundle?.summary}
            topAlerts={bundle?.top_alerts}
            ranking={bundle?.ranking}
            rankingLabel={bundle?.ranking_label}
            rankingKey="work_category"
            rankingValueKey="total_sanctioned"
            showState={false}
            showMp={false}
          />
        </div>
        <div className="border border-line bg-surface p-5">
          <h2 className="font-display text-lg text-ink mb-2">Fund utilization</h2>
          <UtilizationDonut
            disbursed={bundle?.summary?.total_disbursed_amount || 0}
            sanctioned={bundle?.summary?.total_sanctioned_amount || 0}
          />
        </div>
      </div>
    </div>
  );
}
