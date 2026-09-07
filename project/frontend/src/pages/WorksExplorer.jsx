import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import RiskTable from "../components/RiskTable";
import Filters from "../components/Filters";
import { Loading, ErrorState } from "../components/Status";

export default function WorksExplorer() {
  const { user } = useAuth();
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api
      .get("/api/works", { ...filters, page, page_size: 25 })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters, page]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl text-ink">Works</h1>
        <p className="text-sm text-muted mt-1">Browse every sanctioned work visible to your account.</p>
      </div>

      <Filters
        value={filters}
        onChange={(v) => {
          setFilters(v);
          setPage(1);
        }}
        showState={user?.role === "ministry"}
        showDistrict={user?.role === "ministry" || user?.role === "state"}
      />

      {loading && <Loading label="Loading works…" />}
      {error && <ErrorState message={error} />}

      {data && (
        <>
          <RiskTable
            rows={data.items}
            showState={user?.role === "ministry"}
            showMp={user?.role !== "mp"}
          />
          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              Page {data.page} of {data.total_pages} · {data.total.toLocaleString("en-IN")} total
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1 border border-line disabled:opacity-40 hover:border-accent"
              >
                Previous
              </button>
              <button
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 border border-line disabled:opacity-40 hover:border-accent"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
