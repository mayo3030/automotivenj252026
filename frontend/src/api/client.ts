import axios from "axios";

// When the frontend is served by FastAPI (same origin) or by Nginx
// (reverse-proxy), all /api/* requests go to the same host → use "".
// When running the Vite dev server locally, VITE_API_BASE_URL points
// to the backend (http://localhost:8100) and the Vite proxy forwards.
const API_BASE =
  import.meta.env.DEV && import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL
    : "";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

/* ── Date Utility ──────────────────────────────────────────────────────── */

/**
 * Parse an API timestamp string into a proper Date object.
 * Backend stores dates in UTC. If the string lacks a timezone suffix,
 * we append "Z" so JavaScript's Date constructor treats it as UTC
 * instead of local time (which would shift the date for users in
 * different timezones).
 */
export function utcDate(ts: string | null | undefined): Date | null {
  if (!ts) return null;
  const normalized = ts.endsWith("Z") || ts.includes("+") ? ts : ts + "Z";
  return new Date(normalized);
}

/** Format a UTC timestamp string for display in the user's local timezone. */
export function fmtDate(ts: string | null | undefined): string {
  const d = utcDate(ts);
  return d ? d.toLocaleString() : "-";
}

/** Format a UTC timestamp as a short date (no time). */
export function fmtDateShort(ts: string | null | undefined): string {
  const d = utcDate(ts);
  return d ? d.toLocaleDateString() : "-";
}

/* ── Types ─────────────────────────────────────────────────────────────── */

export interface Vehicle {
  id: number;
  stock_number: string | null;
  vin: string;
  year: number | null;
  make: string | null;
  model: string | null;
  trim: string | null;
  price: number | null;
  mileage: number | null;
  exterior_color: string | null;
  interior_color: string | null;
  body_style: string | null;
  drivetrain: string | null;
  engine: string | null;
  transmission: string | null;
  photos: string[];
  detail_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface VehicleList {
  items: Vehicle[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ScrapeLog {
  id: number;
  task_id: string | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  vehicles_found: number;
  vehicles_new: number;
  vehicles_updated: number;
  vehicles_removed: number;
  errors: string[];
  log_output: string;
}

export interface ScrapeLogList {
  items: ScrapeLog[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ScrapeProgress {
  task_id: string | null;
  status: string;
  progress: number;
  vehicles_found: number;
  vehicles_new: number;
  vehicles_updated: number;
  current_page: number;
  total_pages: number;
  message: string;
}

export interface ScrapeTrigger {
  task_id: string;
  message: string;
}

export interface MakeBreakdown {
  make: string;
  count: number;
}

export interface Stats {
  total_vehicles: number;
  active_vehicles: number;
  average_price: number | null;
  makes_breakdown: MakeBreakdown[];
  last_scrape_time: string | null;
  last_scrape_status: string | null;
  total_scrapes: number;
  api_requests_today: number;
}

export interface ApiKeyItem {
  id: number;
  key: string;
  name: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  request_count: number;
}

export interface ApiKeyList {
  items: ApiKeyItem[];
  total: number;
}

/* ── Monitor types ─────────────────────────────────────────────────── */

export interface MonitorConfig {
  enabled: boolean;
  interval_minutes: number;
  last_check_at: string | null;
  last_check_result: string;
  pages_to_scrape: number;
}

export interface MonitorConfigUpdate {
  enabled?: boolean;
  interval_minutes?: number;
  pages_to_scrape?: number;
}

export interface SystemLogItem {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  message: string;
  details: Record<string, any>;
  task_id: string | null;
}

export interface SystemLogList {
  items: SystemLogItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface InventoryComparisonVehicle {
  vin: string;
  year: number | null;
  make: string | null;
  model: string | null;
  price: string | null;
  status: "match" | "missing_local" | "missing_remote" | "changed";
  detail_url: string | null;
}

export interface InventoryComparison {
  website_count: number;
  local_count: number;
  matched: number;
  missing_locally: number;
  extra_locally: number;
  changed: number;
  vehicles: InventoryComparisonVehicle[];
  checked_at: string;
  pages_checked: number;
}

/* ── API Functions ─────────────────────────────────────────────────────── */

export async function fetchVehicles(
  params: Record<string, string | number | boolean | undefined> = {}
): Promise<VehicleList> {
  const cleaned: Record<string, string> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") cleaned[k] = String(v);
  }
  const { data } = await api.get<VehicleList>("/api/vehicles", { params: cleaned });
  return data;
}

export async function fetchVehicle(vin: string): Promise<Vehicle> {
  const { data } = await api.get<Vehicle>(`/api/vehicles/${vin}`);
  return data;
}

export async function searchVehicles(
  q: string,
  page = 1,
  perPage = 20
): Promise<VehicleList> {
  const { data } = await api.get<VehicleList>("/api/vehicles/search", {
    params: { q, page, per_page: perPage },
  });
  return data;
}

export async function triggerScrape(pages: number = 1): Promise<ScrapeTrigger> {
  const { data } = await api.post<ScrapeTrigger>("/api/scrape/trigger", { pages });
  return data;
}

export async function fetchScrapeStatus(
  taskId?: string
): Promise<ScrapeProgress> {
  const params = taskId ? { task_id: taskId } : {};
  const { data } = await api.get<ScrapeProgress>("/api/scrape/status", { params });
  return data;
}

export async function fetchScrapeLogs(
  page = 1,
  perPage = 20
): Promise<ScrapeLogList> {
  const { data } = await api.get<ScrapeLogList>("/api/scrape/logs", {
    params: { page, per_page: perPage },
  });
  return data;
}

export async function fetchStats(): Promise<Stats> {
  const { data } = await api.get<Stats>("/api/stats");
  return data;
}

export async function fetchApiKeys(): Promise<ApiKeyList> {
  const { data } = await api.get<ApiKeyList>("/api/keys");
  return data;
}

export async function createApiKey(name: string): Promise<ApiKeyItem> {
  const { data } = await api.post<ApiKeyItem>("/api/keys", { name });
  return data;
}

export async function revokeApiKey(id: number): Promise<void> {
  await api.delete(`/api/keys/${id}`);
}

/* ── Monitor API Functions ──────────────────────────────────────────── */

export async function fetchMonitorConfig(): Promise<MonitorConfig> {
  const { data } = await api.get<MonitorConfig>("/api/monitor/config");
  return data;
}

export async function updateMonitorConfig(
  update: MonitorConfigUpdate
): Promise<MonitorConfig> {
  const { data } = await api.put<MonitorConfig>("/api/monitor/config", update);
  return data;
}

export async function fetchInventoryComparison(
  pages: number = 0
): Promise<InventoryComparison> {
  const { data } = await api.get<InventoryComparison>("/api/monitor/compare", {
    params: { pages },
    timeout: 300000, // 5 min — Playwright scan can take time for many pages
  });
  return data;
}

export interface SyncProgress {
  status: string;    // "idle" | "starting" | "scanning" | "comparing"
  message: string;
  current_page: number;
  vehicles_found: number;
  total_pages_estimate: number;
}

export async function fetchSyncProgress(): Promise<SyncProgress> {
  const { data } = await api.get<SyncProgress>("/api/monitor/sync-progress");
  return data;
}

export async function fetchSystemLogs(
  page = 1,
  perPage = 50,
  level?: string,
  source?: string
): Promise<SystemLogList> {
  const params: Record<string, string | number> = { page, per_page: perPage };
  if (level) params.level = level;
  if (source) params.source = source;
  const { data } = await api.get<SystemLogList>("/api/monitor/logs", { params });
  return data;
}

export async function clearSystemLogs(): Promise<void> {
  await api.delete("/api/monitor/logs");
}

/* -- Vehicle History types ------------------------------------------- */

export interface PricePoint {
  id: number;
  price: number | null;
  recorded_at: string;
  source: string;
}

export interface ChangeLogEntry {
  id: number;
  vin: string;
  changed_at: string;
  change_type: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  task_id: string | null;
}

export interface VehicleHistory {
  vin: string;
  year: number | null;
  make: string | null;
  model: string | null;
  trim: string | null;
  current_price: number | null;
  first_seen: string | null;
  last_updated: string | null;
  is_active: boolean;
  price_history: PricePoint[];
  change_log: ChangeLogEntry[];
  price_direction: string;
  price_change_amount: number | null;
}

export interface VehicleHistorySummary {
  vin: string;
  year: number | null;
  make: string | null;
  model: string | null;
  trim: string | null;
  current_price: number | null;
  is_active: boolean;
  price_direction: string;
  price_change_amount: number | null;
  total_changes: number;
  last_change_at: string | null;
  hero_photo: string | null;
}

export interface VehicleHistoryList {
  items: VehicleHistorySummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

/* -- Vehicle History API Functions ----------------------------------- */

export async function fetchVehicleHistories(
  page = 1,
  perPage = 20,
  activeOnly = false,
  direction?: string
): Promise<VehicleHistoryList> {
  const params: Record<string, string | number | boolean> = {
    page,
    per_page: perPage,
    active_only: activeOnly,
  };
  if (direction) params.direction = direction;
  const { data } = await api.get<VehicleHistoryList>("/api/history/vehicles", { params });
  return data;
}

export async function fetchVehicleHistory(vin: string): Promise<VehicleHistory> {
  const { data } = await api.get<VehicleHistory>(`/api/history/vehicles/${vin}`);
  return data;
}

export default api;
