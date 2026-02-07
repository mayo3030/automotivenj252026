import { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  fetchVehicleHistories,
  fetchVehicleHistory,
  fmtDate,
  fmtDateShort,
  utcDate,
  type VehicleHistoryList,
  type VehicleHistory,
  type VehicleHistorySummary,
} from "../api/client";
import Spinner from "../components/Spinner";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

/* ====================================================================
   Helper: direction badge
   ==================================================================== */
function DirectionBadge({ dir, amt }: { dir: string; amt: number | null }) {
  if (dir === "up")
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 17a.75.75 0 0 1-.75-.75V5.612L5.29 9.77a.75.75 0 0 1-1.08-1.04l5.25-5.5a.75.75 0 0 1 1.08 0l5.25 5.5a.75.75 0 1 1-1.08 1.04l-3.96-4.158V16.25A.75.75 0 0 1 10 17Z" clipRule="evenodd" /></svg>
        +${Math.abs(amt ?? 0).toLocaleString()}
      </span>
    );
  if (dir === "down")
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
        <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 3a.75.75 0 0 1 .75.75v10.638l3.96-4.158a.75.75 0 1 1 1.08 1.04l-5.25 5.5a.75.75 0 0 1-1.08 0l-5.25-5.5a.75.75 0 1 1 1.08-1.04l3.96 4.158V3.75A.75.75 0 0 1 10 3Z" clipRule="evenodd" /></svg>
        -${Math.abs(amt ?? 0).toLocaleString()}
      </span>
    );
  if (dir === "new")
    return <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">New</span>;
  return <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500">Stable</span>;
}

/* ====================================================================
   Change-type badge
   ==================================================================== */
function ChangeTypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    new: "bg-blue-100 text-blue-700",
    updated: "bg-yellow-100 text-yellow-700",
    removed: "bg-red-100 text-red-700",
    reactivated: "bg-green-100 text-green-700",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${map[type] || "bg-gray-100 text-gray-600"}`}>
      {type}
    </span>
  );
}

/* ====================================================================
   Price chart component for a single vehicle
   ==================================================================== */
function PriceChart({ history }: { history: VehicleHistory }) {
  const data = history.price_history
    .filter((p) => p.price !== null)
    .map((p) => ({
      date: fmtDateShort(p.recorded_at),
      fullDate: fmtDate(p.recorded_at),
      price: p.price,
    }));

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-gray-400 text-sm">
        No price data recorded yet
      </div>
    );
  }

  // If only one data point, show it as a reference line
  if (data.length === 1) {
    return (
      <div className="flex h-48 items-center justify-center flex-col gap-2">
        <p className="text-3xl font-bold text-gray-800">${data[0].price?.toLocaleString()}</p>
        <p className="text-xs text-gray-400">First recorded: {data[0].fullDate}</p>
        <p className="text-xs text-gray-400 italic">More data points will appear after future scrapes</p>
      </div>
    );
  }

  const prices = data.map((d) => d.price!);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const pad = Math.max((maxP - minP) * 0.15, 500);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9ca3af" />
        <YAxis
          domain={[Math.floor(minP - pad), Math.ceil(maxP + pad)]}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
          tick={{ fontSize: 11 }} stroke="#9ca3af" width={55}
        />
        <Tooltip
          formatter={(value: any) => [`$${Number(value).toLocaleString()}`, "Price"]}
          labelFormatter={(label: any) => String(label)}
          contentStyle={{ borderRadius: 8, fontSize: 13 }}
        />
        {history.current_price && (
          <ReferenceLine y={history.current_price} stroke="#9ca3af" strokeDasharray="3 3" label="" />
        )}
        <Line
          type="stepAfter" dataKey="price" stroke="#4f46e5" strokeWidth={2.5}
          dot={{ r: 4, fill: "#4f46e5" }} activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ====================================================================
   Detail View: one vehicle's full history
   ==================================================================== */
function VehicleDetailHistory({ vin, onBack }: { vin: string; onBack: () => void }) {
  const [history, setHistory] = useState<VehicleHistory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchVehicleHistory(vin)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [vin]);

  if (loading) return <div className="py-20 text-center"><Spinner size="lg" /></div>;
  if (!history) return <div className="py-20 text-center text-gray-500">Vehicle not found</div>;

  const title = `${history.year || ""} ${history.make || ""} ${history.model || ""} ${history.trim || ""}`.trim();

  return (
    <div className="space-y-6">
      {/* Back + title */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="rounded-lg border border-gray-300 bg-white p-2 hover:bg-gray-50">
          <svg className="h-4 w-4 text-gray-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" /></svg>
        </button>
        <div>
          <h2 className="text-xl font-bold text-gray-900">{title || "Unknown Vehicle"}</h2>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <span className="font-mono">{history.vin}</span>
            <span className={history.is_active ? "text-green-600" : "text-red-500"}>
              {history.is_active ? "Active" : "Inactive"}
            </span>
            <DirectionBadge dir={history.price_direction} amt={history.price_change_amount} />
          </div>
        </div>
        <div className="ml-auto text-right">
          <p className="text-2xl font-bold text-gray-900">
            {history.current_price ? `$${history.current_price.toLocaleString()}` : "N/A"}
          </p>
          <p className="text-xs text-gray-400">Current Price</p>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500">First Seen</p>
          <p className="text-sm font-semibold">{fmtDateShort(history.first_seen)}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500">Last Updated</p>
          <p className="text-sm font-semibold">{fmtDateShort(history.last_updated)}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500">Price Records</p>
          <p className="text-sm font-semibold">{history.price_history.length}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-xs text-gray-500">Total Changes</p>
          <p className="text-sm font-semibold">{history.change_log.length}</p>
        </div>
      </div>

      {/* Price chart */}
      <div className="card p-5">
        <h3 className="mb-3 text-base font-semibold text-gray-900">Price History</h3>
        <PriceChart history={history} />
      </div>

      {/* Change timeline */}
      <div className="card p-5">
        <h3 className="mb-4 text-base font-semibold text-gray-900">Change Timeline</h3>
        {history.change_log.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No changes recorded yet</p>
        ) : (
          <div className="relative ml-4 border-l-2 border-gray-200 pl-6 space-y-5">
            {history.change_log.map((c) => (
              <div key={c.id} className="relative">
                {/* Dot */}
                <div className={`absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white ${
                  c.change_type === "new" ? "bg-blue-500" :
                  c.change_type === "removed" ? "bg-red-500" :
                  c.change_type === "reactivated" ? "bg-green-500" : "bg-yellow-500"
                }`} />
                <div className="flex flex-wrap items-start gap-2">
                  <ChangeTypeBadge type={c.change_type} />
                  <span className="text-xs text-gray-400">
                    {fmtDate(c.changed_at)}
                  </span>
                </div>
                {c.field_name && (
                  <p className="mt-1 text-sm text-gray-700">
                    <span className="font-medium capitalize">{c.field_name.replace(/_/g, " ")}</span>
                    {c.old_value && c.new_value ? (
                      <> changed from <span className="font-mono text-red-600 bg-red-50 px-1 rounded">{c.old_value}</span> to <span className="font-mono text-green-600 bg-green-50 px-1 rounded">{c.new_value}</span></>
                    ) : c.new_value ? (
                      <> set to <span className="font-mono text-green-600 bg-green-50 px-1 rounded">{c.new_value}</span></>
                    ) : null}
                  </p>
                )}
                {c.change_type === "new" && <p className="mt-1 text-sm text-gray-600">Vehicle first appeared in inventory</p>}
                {c.change_type === "removed" && <p className="mt-1 text-sm text-gray-600">Vehicle removed from live inventory</p>}
                {c.change_type === "reactivated" && <p className="mt-1 text-sm text-gray-600">Vehicle reappeared in inventory</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Link to inventory detail */}
      <div className="text-center">
        <Link to={`/inventory/${history.vin}`} className="text-sm text-brand-600 hover:text-brand-700 font-medium">
          View full vehicle details &rarr;
        </Link>
      </div>
    </div>
  );
}

/* ====================================================================
   Main History Page
   ==================================================================== */
export default function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedVin = searchParams.get("vin");

  const [list, setList] = useState<VehicleHistoryList | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchVehicleHistories(page, 20, false, filter || undefined);
      setList(data);
    } catch {}
    setLoading(false);
  }, [page, filter]);

  useEffect(() => { loadList(); }, [loadList]);

  // Detail view
  if (selectedVin) {
    return (
      <VehicleDetailHistory
        vin={selectedVin}
        onBack={() => setSearchParams({})}
      />
    );
  }

  // List view
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Vehicle History</h1>
        <p className="mt-1 text-sm text-gray-500">
          Track price changes and all updates for every vehicle. Click a vehicle to see its full chart and timeline.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Price Direction</label>
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
          >
            <option value="">All Vehicles</option>
            <option value="down">Price Dropped</option>
            <option value="up">Price Increased</option>
            <option value="stable">Price Stable</option>
            <option value="new">New (single price)</option>
          </select>
        </div>
        <button onClick={loadList} className="mt-5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
          Refresh
        </button>
        {list && <span className="mt-5 text-sm text-gray-400">{list.total} vehicles</span>}
      </div>

      {/* Vehicle list */}
      {loading && !list ? (
        <div className="py-20 text-center"><Spinner size="lg" /><p className="mt-2 text-sm text-gray-400">Loading histories...</p></div>
      ) : !list || list.items.length === 0 ? (
        <div className="card p-12 text-center text-gray-500">
          <p className="font-medium">No vehicle history yet</p>
          <p className="text-xs mt-1">Run a scrape to start tracking price changes.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {list.items.map((v: VehicleHistorySummary) => (
              <button
                key={v.vin}
                onClick={() => setSearchParams({ vin: v.vin })}
                className="card flex items-center gap-4 p-4 text-left hover:ring-2 hover:ring-brand-500/30 transition-all"
              >
                {/* Hero thumbnail */}
                <div className="h-16 w-24 flex-shrink-0 overflow-hidden rounded-lg bg-gray-100">
                  {v.hero_photo ? (
                    <img src={v.hero_photo} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-gray-300">
                      <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" /></svg>
                    </div>
                  )}
                </div>

                {/* Vehicle info */}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">
                    {v.year} {v.make} {v.model} {v.trim || ""}
                  </p>
                  <p className="text-xs text-gray-500 font-mono">{v.vin}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs ${v.is_active ? "text-green-600" : "text-red-500"}`}>
                      {v.is_active ? "Active" : "Inactive"}
                    </span>
                    <span className="text-xs text-gray-400">
                      {v.total_changes} change{v.total_changes !== 1 ? "s" : ""}
                    </span>
                    {v.last_change_at && (
                      <span className="text-xs text-gray-400">
                        Last: {fmtDateShort(v.last_change_at)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Price + direction */}
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <p className="text-lg font-bold text-gray-900">
                    {v.current_price ? `$${v.current_price.toLocaleString()}` : "N/A"}
                  </p>
                  <DirectionBadge dir={v.price_direction} amt={v.price_change_amount} />
                </div>

                {/* Arrow */}
                <svg className="h-5 w-5 text-gray-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
              </button>
            ))}
          </div>

          {/* Pagination */}
          {list.pages > 1 && (
            <div className="flex items-center justify-between">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >Previous</button>
              <span className="text-sm text-gray-500">Page {list.page} of {list.pages}</span>
              <button
                onClick={() => setPage((p) => Math.min(list!.pages, p + 1))}
                disabled={page >= list.pages}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
