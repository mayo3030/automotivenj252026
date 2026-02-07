import { useCallback } from "react";
import { Link } from "react-router-dom";
import { fetchStats, fmtDate, type Stats } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import StatCard from "../components/StatCard";
import Spinner from "../components/Spinner";

export default function Dashboard() {
  const fetcher = useCallback(() => fetchStats(), []);
  const { data: stats, loading, error } = useFetch<Stats>(fetcher);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
        <h3 className="font-semibold">Error loading stats</h3>
        <p className="mt-1 text-sm">{error.message}</p>
      </div>
    );
  }

  if (!stats) return null;

  const lastScrape = stats.last_scrape_time
    ? fmtDate(stats.last_scrape_time)
    : "Never";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your vehicle inventory and scraping activity.
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Vehicles"
          value={stats.active_vehicles}
          sub={`${stats.total_vehicles} total`}
          color="blue"
        />
        <StatCard
          label="Average Price"
          value={stats.average_price ? `$${stats.average_price.toLocaleString()}` : "N/A"}
          color="green"
        />
        <StatCard
          label="Last Scrape"
          value={lastScrape}
          sub={stats.last_scrape_status || ""}
          color={stats.last_scrape_status === "completed" ? "green" : "amber"}
        />
        <StatCard
          label="Total Scrapes"
          value={stats.total_scrapes}
          sub={`${stats.api_requests_today} API requests today`}
          color="purple"
        />
      </div>

      {/* Makes Breakdown */}
      {stats.makes_breakdown.length > 0 && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Inventory by Make</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {stats.makes_breakdown.map((m) => (
              <Link
                key={m.make}
                to={`/inventory?make=${encodeURIComponent(m.make)}`}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 transition-colors hover:bg-brand-50 hover:border-brand-200"
              >
                <span className="font-medium text-sm text-gray-800">{m.make}</span>
                <span className="badge bg-brand-100 text-brand-700">{m.count}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link to="/scrape" className="btn-primary">
            <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
            </svg>
            Run Scraper
          </Link>
          <Link to="/inventory" className="btn-secondary">
            View Inventory
          </Link>
          <Link to="/api-docs" className="btn-secondary">
            API Documentation
          </Link>
        </div>
      </div>
    </div>
  );
}
