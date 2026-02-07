import { useState, useCallback, useEffect, useRef } from "react";
import {
  fetchSystemLogs,
  clearSystemLogs,
  fmtDate,
  type SystemLogList,
  type SystemLogItem,
} from "../api/client";
import Spinner from "../components/Spinner";

const LEVEL_COLORS: Record<string, string> = {
  debug: "bg-gray-100 text-gray-600",
  info: "bg-blue-100 text-blue-700",
  warning: "bg-yellow-100 text-yellow-700",
  error: "bg-red-100 text-red-700",
  critical: "bg-red-200 text-red-800",
};

const SOURCE_COLORS: Record<string, string> = {
  scraper: "bg-indigo-100 text-indigo-700",
  monitor: "bg-purple-100 text-purple-700",
  api: "bg-teal-100 text-teal-700",
};

export default function Logs() {
  const [logs, setLogs] = useState<SystemLogList | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadLogs = useCallback(async () => {
    try {
      const data = await fetchSystemLogs(
        page, 50,
        levelFilter || undefined,
        sourceFilter || undefined
      );
      setLogs(data);
    } catch {
      // ignore errors silently
    } finally {
      setLoading(false);
    }
  }, [page, levelFilter, sourceFilter]);

  // Initial load & filter changes
  useEffect(() => {
    setLoading(true);
    loadLogs();
  }, [loadLogs]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshRef.current = setInterval(loadLogs, 5000);
    }
    return () => {
      if (autoRefreshRef.current) {
        clearInterval(autoRefreshRef.current);
        autoRefreshRef.current = null;
      }
    };
  }, [autoRefresh, loadLogs]);

  async function handleClear() {
    if (!confirm("Clear all system logs? This cannot be undone.")) return;
    try {
      await clearSystemLogs();
      loadLogs();
    } catch {}
  }

  function formatTime(ts: string) {
    return fmtDate(ts);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Logs</h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time debug and error logs from the scraper, monitor, and API.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              autoRefresh
                ? "bg-green-100 text-green-700 hover:bg-green-200"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            <span className={`inline-block h-2 w-2 rounded-full ${autoRefresh ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
            {autoRefresh ? "Live" : "Paused"}
          </button>

          <button
            onClick={loadLogs}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Refresh
          </button>

          <button
            onClick={handleClear}
            className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Clear Logs
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Level</label>
            <select
              value={levelFilter}
              onChange={(e) => { setLevelFilter(e.target.value); setPage(1); }}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All Levels</option>
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Source</label>
            <select
              value={sourceFilter}
              onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All Sources</option>
              <option value="scraper">Scraper</option>
              <option value="monitor">Monitor</option>
              <option value="api">API</option>
            </select>
          </div>

          {logs && (
            <div className="ml-auto text-sm text-gray-500">
              {logs.total} total logs
              {logs.pages > 1 && ` | Page ${logs.page}/${logs.pages}`}
            </div>
          )}
        </div>
      </div>

      {/* Logs Table */}
      <div className="card overflow-hidden">
        {loading && !logs ? (
          <div className="p-12 text-center">
            <Spinner size="lg" />
            <p className="mt-2 text-sm text-gray-500">Loading logs...</p>
          </div>
        ) : !logs || logs.items.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            <p className="mt-2 text-sm font-medium">No logs yet</p>
            <p className="text-xs">Enable the monitor or run a scrape to see logs here.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium w-40">Timestamp</th>
                    <th className="px-3 py-2 text-left font-medium w-20">Level</th>
                    <th className="px-3 py-2 text-left font-medium w-24">Source</th>
                    <th className="px-3 py-2 text-left font-medium">Message</th>
                    <th className="px-3 py-2 text-left font-medium w-32">Task ID</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.items.map((log: SystemLogItem) => (
                    <tr
                      key={log.id}
                      className={`border-b border-gray-100 hover:bg-gray-50 ${
                        log.level === "error" || log.level === "critical" ? "bg-red-50/50" :
                        log.level === "warning" ? "bg-yellow-50/50" : ""
                      }`}
                    >
                      <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                        {formatTime(log.timestamp)}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium uppercase ${
                          LEVEL_COLORS[log.level] || "bg-gray-100 text-gray-600"
                        }`}>
                          {log.level}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          SOURCE_COLORS[log.source] || "bg-gray-100 text-gray-600"
                        }`}>
                          {log.source}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-700">
                        <div className="max-w-xl">
                          <p className="truncate">{log.message}</p>
                          {log.details && Object.keys(log.details).length > 0 && (
                            <p className="mt-0.5 text-xs text-gray-400 font-mono truncate">
                              {JSON.stringify(log.details)}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-400 font-mono">
                        {log.task_id ? log.task_id.slice(0, 16) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {logs.pages > 1 && (
              <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page {logs.page} of {logs.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(logs!.pages, p + 1))}
                  disabled={page >= logs.pages}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
