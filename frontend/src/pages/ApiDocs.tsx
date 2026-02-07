import { useState, useCallback } from "react";
import {
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  type ApiKeyList,
} from "../api/client";
import { useFetch } from "../hooks/useFetch";
import Spinner from "../components/Spinner";

const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin;
const DISPLAY_BASE = API_BASE.includes("localhost") ? API_BASE : window.location.origin;

export default function ApiDocs() {
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const keysFetcher = useCallback(() => fetchApiKeys(), []);
  const {
    data: keysData,
    loading,
    refetch,
  } = useFetch<ApiKeyList>(keysFetcher);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    try {
      setCreating(true);
      await createApiKey(newKeyName.trim());
      setNewKeyName("");
      refetch();
    } catch (err) {
      console.error("Failed to create API key:", err);
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: number) {
    if (!confirm("Are you sure you want to revoke this API key?")) return;
    try {
      await revokeApiKey(id);
      refetch();
    } catch (err) {
      console.error("Failed to revoke API key:", err);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text);
    setCopiedKey(text);
    setTimeout(() => setCopiedKey(null), 2000);
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">API Documentation</h1>
        <p className="mt-1 text-sm text-gray-500">
          Programmatic access to the AutoAvenue vehicle inventory data.
        </p>
      </div>

      {/* Swagger Link */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Interactive API Explorer</h2>
        <p className="text-sm text-gray-600 mb-4">
          The backend provides a Swagger UI with full endpoint documentation, request/response
          schemas, and an interactive &quot;Try it out&quot; feature.
        </p>
        <a
          href={`${DISPLAY_BASE}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-primary"
        >
          Open Swagger UI
          <svg className="ml-2 h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
        </a>
      </div>

      {/* Code Examples */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Code Examples</h2>
        </div>
        <div className="p-6 space-y-6">
          {/* cURL */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">cURL</h3>
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-sm text-green-400">
{`# List all vehicles
curl -H "X-API-Key: YOUR_KEY" \\
  "${DISPLAY_BASE}/api/vehicles?page=1&per_page=20"

# Get vehicle by VIN
curl -H "X-API-Key: YOUR_KEY" \\
  "${DISPLAY_BASE}/api/vehicles/1HGBH41JXMN109186"

# Search vehicles
curl -H "X-API-Key: YOUR_KEY" \\
  "${DISPLAY_BASE}/api/vehicles/search?q=BMW"

# Trigger a scrape
curl -X POST -H "X-API-Key: YOUR_KEY" \\
  "${DISPLAY_BASE}/api/scrape/trigger"

# Get stats
curl -H "X-API-Key: YOUR_KEY" \\
  "${DISPLAY_BASE}/api/stats"`}
            </pre>
          </div>

          {/* Python */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Python (requests)</h3>
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-sm text-green-400">
{`import requests

API_BASE = "${DISPLAY_BASE}"
HEADERS = {"X-API-Key": "YOUR_KEY"}

# List vehicles with filters
resp = requests.get(f"{API_BASE}/api/vehicles", headers=HEADERS, params={
    "make": "BMW",
    "year_min": 2020,
    "price_max": 60000,
    "sort_by": "price",
    "order": "asc",
})
data = resp.json()
for v in data["items"]:
    print(f"{v['year']} {v['make']} {v['model']} - \${v['price']}")`}
            </pre>
          </div>

          {/* JavaScript */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">JavaScript (fetch)</h3>
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-sm text-green-400">
{`const API_BASE = "${DISPLAY_BASE}";
const API_KEY = "YOUR_KEY";

const response = await fetch(\`\${DISPLAY_BASE}/api/vehicles?per_page=50\`, {
  headers: { "X-API-Key": API_KEY },
});
const data = await response.json();
console.log(\`Total vehicles: \${data.total}\`);
data.items.forEach(v => {
  console.log(\`\${v.year} \${v.make} \${v.model} - $\${v.price}\`);
});`}
            </pre>
          </div>
        </div>
      </div>

      {/* Endpoints Reference */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Endpoints Reference</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Method</th>
                <th className="px-4 py-3 text-left font-medium">Endpoint</th>
                <th className="px-4 py-3 text-left font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {[
                ["GET", "/api/vehicles", "Paginated list with filters & sorting"],
                ["GET", "/api/vehicles/search?q=", "Search by VIN, stock#, make, or model"],
                ["GET", "/api/vehicles/export", "Export as CSV, JSON, or PDF"],
                ["GET", "/api/vehicles/{vin}", "Single vehicle detail"],
                ["POST", "/api/scrape/trigger", "Start a new scrape job"],
                ["GET", "/api/scrape/status", "Current scrape progress"],
                ["GET", "/api/scrape/logs", "Scrape run history"],
                ["GET", "/api/stats", "Dashboard statistics"],
                ["GET", "/api/keys", "List API keys"],
                ["POST", "/api/keys", "Create a new API key"],
                ["DELETE", "/api/keys/{id}", "Revoke an API key"],
              ].map(([method, endpoint, desc], i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span
                      className={`badge font-mono ${
                        method === "GET"
                          ? "bg-green-100 text-green-700"
                          : method === "POST"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {method}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-700">{endpoint}</td>
                  <td className="px-4 py-3 text-gray-500">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* API Key Management */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">API Key Management</h2>
          <p className="mt-1 text-xs text-gray-500">
            API keys authenticate external consumers. Pass via <code className="bg-gray-100 px-1 rounded">X-API-Key</code> header.
          </p>
        </div>

        <div className="p-6">
          {/* Create new key */}
          <form onSubmit={handleCreate} className="flex gap-2 mb-6">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g. My Integration)"
              className="input-field flex-1"
            />
            <button type="submit" disabled={creating || !newKeyName.trim()} className="btn-primary text-sm">
              {creating ? <Spinner size="sm" /> : "Generate Key"}
            </button>
          </form>

          {/* Key list */}
          {loading ? (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          ) : keysData && keysData.items.length > 0 ? (
            <div className="space-y-3">
              {keysData.items.map((k) => (
                <div
                  key={k.id}
                  className={`flex items-center justify-between rounded-lg border p-4 ${
                    k.is_active
                      ? "border-gray-200 bg-white"
                      : "border-gray-100 bg-gray-50 opacity-60"
                  }`}
                >
                  <div className="space-y-1 overflow-hidden">
                    <p className="font-medium text-gray-900">{k.name}</p>
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-gray-500 font-mono truncate max-w-xs">
                        {k.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(k.key)}
                        className="text-gray-400 hover:text-brand-600 transition-colors"
                        title="Copy key"
                      >
                        {copiedKey === k.key ? (
                          <svg className="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
                          </svg>
                        )}
                      </button>
                    </div>
                    <p className="text-xs text-gray-400">
                      Created {new Date(k.created_at).toLocaleDateString()} &middot;{" "}
                      {k.request_count} requests
                      {k.last_used_at && ` · Last used ${new Date(k.last_used_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {k.is_active ? (
                      <button
                        onClick={() => handleRevoke(k.id)}
                        className="btn-danger text-xs"
                      >
                        Revoke
                      </button>
                    ) : (
                      <span className="badge bg-gray-200 text-gray-500">Revoked</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-sm text-gray-500 py-6">
              No API keys created yet. Generate one above.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
