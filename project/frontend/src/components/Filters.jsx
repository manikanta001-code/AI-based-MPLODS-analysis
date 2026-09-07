import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Filters({ value, onChange, showState = true, showDistrict = false }) {
  const [meta, setMeta] = useState({ states: [], categories: [], statuses: [], districts: [] });

  useEffect(() => {
    Promise.all([
      api.get("/api/meta/states"),
      api.get("/api/meta/categories"),
      api.get("/api/meta/statuses"),
      showDistrict ? api.get("/api/meta/districts") : Promise.resolve([]),
    ]).then(([states, categories, statuses, districts]) => {
      setMeta({ states, categories, statuses, districts });
    });
  }, [showDistrict]);

  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value || undefined });

  const selectClass =
    "border border-line bg-surface text-sm px-3 py-1.5 focus:border-accent outline-none min-w-[9rem]";

  return (
    <div className="flex flex-wrap gap-2">
      <input
        type="text"
        placeholder="Search Work ID or description…"
        value={value.search || ""}
        onChange={set("search")}
        className={`${selectClass} min-w-[16rem]`}
      />
      {showState && (
        <select className={selectClass} value={value.state || ""} onChange={set("state")}>
          <option value="">All states</option>
          {meta.states.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      )}
      {showDistrict && (
        <select className={selectClass} value={value.ida || ""} onChange={set("ida")}>
          <option value="">All districts</option>
          {meta.districts.map((d) => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
      )}
      <select className={selectClass} value={value.work_category || ""} onChange={set("work_category")}>
        <option value="">All categories</option>
        {meta.categories.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <select className={selectClass} value={value.work_status || ""} onChange={set("work_status")}>
        <option value="">All statuses</option>
        {meta.statuses.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <select className={selectClass} value={value.risk_band || ""} onChange={set("risk_band")}>
        <option value="">All risk bands</option>
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
      </select>
    </div>
  );
}
