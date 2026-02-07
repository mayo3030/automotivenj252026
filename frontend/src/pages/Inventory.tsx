import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  fetchVehicles,
  searchVehicles,
  type VehicleList,
} from "../api/client";
import { useFetch } from "../hooks/useFetch";
import VehicleCard from "../components/VehicleCard";
import Pagination from "../components/Pagination";
import Spinner from "../components/Spinner";

type ViewMode = "grid" | "table";

export default function Inventory() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [view, setView] = useState<ViewMode>("grid");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [filters, setFilters] = useState({
    make: searchParams.get("make") || "",
    model: searchParams.get("model") || "",
    year_min: searchParams.get("year_min") || "",
    year_max: searchParams.get("year_max") || "",
    price_min: searchParams.get("price_min") || "",
    price_max: searchParams.get("price_max") || "",
    body_style: searchParams.get("body_style") || "",
    sort_by: searchParams.get("sort_by") || "created_at",
    order: searchParams.get("order") || "desc",
  });

  const fetcher = useCallback(() => {
    if (search.trim()) {
      return searchVehicles(search, page, 20);
    }
    return fetchVehicles({ ...filters, page, per_page: 20 });
  }, [search, page, filters]);

  const { data, loading, error, refetch } = useFetch<VehicleList>(fetcher, [
    search,
    page,
    filters.make,
    filters.model,
    filters.sort_by,
    filters.order,
    filters.year_min,
    filters.year_max,
    filters.price_min,
    filters.price_max,
    filters.body_style,
  ]);

  // Update URL search params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (search) params.q = search;
    if (page > 1) params.page = String(page);
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params[k] = v;
    });
    setSearchParams(params, { replace: true });
  }, [search, page, filters]);

  function handleFilterChange(key: string, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    refetch();
  }

  const exportUrl = (format: string) => {
    return `/api/vehicles/export?format=${format}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Vehicle Inventory</h1>
          <p className="mt-1 text-sm text-gray-500">
            {data ? `${data.total} vehicles found` : "Loading..."}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <div className="flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setView("grid")}
              className={`px-3 py-1.5 text-xs font-medium ${
                view === "grid"
                  ? "bg-brand-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              Grid
            </button>
            <button
              onClick={() => setView("table")}
              className={`px-3 py-1.5 text-xs font-medium ${
                view === "table"
                  ? "bg-brand-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              Table
            </button>
          </div>

          {/* Export */}
          <div className="relative group">
            <button className="btn-secondary text-xs">
              Export
              <svg className="ml-1 h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            <div className="absolute right-0 mt-1 hidden w-32 rounded-lg border border-gray-200 bg-white py-1 shadow-lg group-hover:block z-10">
              <a href={exportUrl("csv")} className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                CSV
              </a>
              <a href={exportUrl("json")} className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                JSON
              </a>
              <a href={exportUrl("pdf")} className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                PDF
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="card p-4">
        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by VIN, stock number, make, or model..."
            className="input-field flex-1"
          />
          <button type="submit" className="btn-primary text-sm">
            Search
          </button>
          {search && (
            <button
              type="button"
              onClick={() => { setSearch(""); setPage(1); }}
              className="btn-secondary text-sm"
            >
              Clear
            </button>
          )}
        </form>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <input
            type="text"
            value={filters.make}
            onChange={(e) => handleFilterChange("make", e.target.value)}
            placeholder="Make"
            className="input-field text-sm"
          />
          <input
            type="text"
            value={filters.model}
            onChange={(e) => handleFilterChange("model", e.target.value)}
            placeholder="Model"
            className="input-field text-sm"
          />
          <input
            type="number"
            value={filters.year_min}
            onChange={(e) => handleFilterChange("year_min", e.target.value)}
            placeholder="Year Min"
            className="input-field text-sm"
          />
          <input
            type="number"
            value={filters.year_max}
            onChange={(e) => handleFilterChange("year_max", e.target.value)}
            placeholder="Year Max"
            className="input-field text-sm"
          />
          <input
            type="number"
            value={filters.price_min}
            onChange={(e) => handleFilterChange("price_min", e.target.value)}
            placeholder="Price Min"
            className="input-field text-sm"
          />
          <input
            type="number"
            value={filters.price_max}
            onChange={(e) => handleFilterChange("price_max", e.target.value)}
            placeholder="Price Max"
            className="input-field text-sm"
          />
        </div>

        <div className="flex items-center gap-3 mt-3">
          <select
            value={filters.sort_by}
            onChange={(e) => handleFilterChange("sort_by", e.target.value)}
            className="input-field w-auto text-sm"
          >
            <option value="created_at">Date Added</option>
            <option value="price">Price</option>
            <option value="year">Year</option>
            <option value="mileage">Mileage</option>
            <option value="make">Make</option>
          </select>
          <select
            value={filters.order}
            onChange={(e) => handleFilterChange("order", e.target.value)}
            className="input-field w-auto text-sm"
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-10">
          <Spinner size="lg" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
          <p className="font-semibold">Error loading vehicles</p>
          <p className="mt-1 text-sm">{error.message}</p>
        </div>
      )}

      {/* Results */}
      {data && !loading && (
        <>
          {data.items.length === 0 ? (
            <div className="card p-12 text-center text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <p className="mt-3 text-lg font-medium">No vehicles found</p>
              <p className="mt-1 text-sm">Try adjusting your filters or search query.</p>
            </div>
          ) : view === "grid" ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {data.items.map((v) => (
                <VehicleCard key={v.vin} vehicle={v} view="grid" />
              ))}
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Vehicle</th>
                    <th className="px-4 py-3 text-left font-medium">VIN</th>
                    <th className="px-4 py-3 text-left font-medium">Price</th>
                    <th className="px-4 py-3 text-left font-medium">Mileage</th>
                    <th className="px-4 py-3 text-left font-medium">Color</th>
                    <th className="px-4 py-3 text-left font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((v) => (
                    <VehicleCard key={v.vin} vehicle={v} view="table" />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Pagination
            page={data.page}
            pages={data.pages}
            onPageChange={(p) => setPage(p)}
          />
        </>
      )}
    </div>
  );
}
