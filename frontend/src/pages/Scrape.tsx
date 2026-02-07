import { useState, useCallback, useEffect, useRef } from "react";
import {
  triggerScrape,
  fetchScrapeStatus,
  fetchScrapeLogs,
  fetchMonitorConfig,
  updateMonitorConfig,
  fetchInventoryComparison,
  fetchSyncProgress,
  fmtDate,
  utcDate,
  type ScrapeProgress,
  type ScrapeLogList,
  type MonitorConfig,
  type InventoryComparison,
  type InventoryComparisonVehicle,
  type SyncProgress,
} from "../api/client";
import { useFetch } from "../hooks/useFetch";
import Spinner from "../components/Spinner";

/* ================================================================
   Helpers
   ================================================================ */

function cls(...classes: (string | false | undefined | null)[]) {
  return classes.filter(Boolean).join(" ");
}

/** Animate a number counting up */
function AnimatedNumber({ value, duration = 600 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const start = prev.current;
    const diff = value - start;
    if (diff === 0) { setDisplay(value); return; }
    const startTime = performance.now();
    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out
      setDisplay(Math.round(start + diff * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    prev.current = value;
  }, [value, duration]);
  return <>{display.toLocaleString()}</>;
}

/* ================================================================
   SVG Icons (inline, no deps)
   ================================================================ */

const icons = {
  bolt: (
    <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
  ),
  sync: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  ),
  check: (
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  ),
  checkBadge: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
  ),
  warning: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  ),
  refresh: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
  ),
  search: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
  ),
  globe: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" />
  ),
  database: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
  ),
  plus: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  ),
  minus: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12h-15" />
  ),
  error: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
  ),
  x: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
  ),
  clock: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  ),
  doc: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
  ),
  signal: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.348 14.652a3.75 3.75 0 0 1 0-5.304m5.304 0a3.75 3.75 0 0 1 0 5.304m-7.425 2.121a6.75 6.75 0 0 1 0-9.546m9.546 0a6.75 6.75 0 0 1 0 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.807 3.808 9.98 0 13.788M12 12h.008v.008H12V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
  ),
};

function Icon({ d, className = "h-5 w-5", sw = 2 }: { d: React.ReactNode; className?: string; sw?: number }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={sw} stroke="currentColor">{d}</svg>
  );
}

/* ================================================================
   Sub-components
   ================================================================ */

/* -- Step indicator ------------------------------------------------ */

type StepStatus = "pending" | "active" | "completed";

function StepIndicator({ steps, current }: { steps: { label: string; sub: string }[]; current: number }) {
  return (
    <nav aria-label="Progress" className="mb-8">
      <ol className="flex items-center">
        {steps.map(({ label, sub }, idx) => {
          const status: StepStatus =
            idx < current ? "completed" : idx === current ? "active" : "pending";
          const isLast = idx === steps.length - 1;
          return (
            <li key={label} className={cls("flex items-center", !isLast && "flex-1")}>
              <div className="flex items-center gap-3">
                <span
                  className={cls(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold transition-all duration-500",
                    status === "completed" && "bg-green-500 text-white shadow-lg shadow-green-200",
                    status === "active" && "bg-brand-600 text-white shadow-lg shadow-brand-200 ring-4 ring-brand-100",
                    status === "pending" && "bg-gray-100 text-gray-400 border-2 border-gray-200",
                  )}
                >
                  {status === "completed" ? (
                    <Icon d={icons.check} className="h-5 w-5" sw={3} />
                  ) : (
                    idx + 1
                  )}
                </span>
                <div className="hidden sm:block">
                  <p className={cls(
                    "text-sm font-semibold leading-tight",
                    status === "active" ? "text-brand-700" : status === "completed" ? "text-green-700" : "text-gray-400",
                  )}>{label}</p>
                  <p className={cls(
                    "text-xs",
                    status === "active" ? "text-brand-500" : status === "completed" ? "text-green-500" : "text-gray-300",
                  )}>{sub}</p>
                </div>
              </div>
              {!isLast && (
                <div className="ml-3 flex-1 sm:ml-4">
                  <div className="h-1 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={cls(
                        "h-full rounded-full transition-all duration-700",
                        idx < current ? "w-full bg-green-400" : "w-0 bg-brand-400",
                      )}
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* -- Sync result cards ---------------------------------------------- */

interface SyncCardProps {
  label: string;
  value: number;
  color: "blue" | "purple" | "green" | "red" | "yellow" | "orange";
  icon: React.ReactNode;
  subtitle?: string;
  highlight?: boolean;
}

function SyncCard({ label, value, color, icon, subtitle, highlight }: SyncCardProps) {
  const colors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
    blue:   { bg: "bg-blue-50",   border: "border-blue-200",   text: "text-blue-700",   badge: "bg-blue-100 text-blue-600" },
    purple: { bg: "bg-purple-50", border: "border-purple-200", text: "text-purple-700", badge: "bg-purple-100 text-purple-600" },
    green:  { bg: "bg-green-50",  border: "border-green-200",  text: "text-green-700",  badge: "bg-green-100 text-green-600" },
    red:    { bg: "bg-red-50",    border: "border-red-200",    text: "text-red-700",    badge: "bg-red-100 text-red-600" },
    yellow: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-700", badge: "bg-yellow-100 text-yellow-600" },
    orange: { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-700", badge: "bg-orange-100 text-orange-600" },
  };
  const c = colors[color];

  return (
    <div className={cls(
      "rounded-xl border p-5 transition-all duration-300 hover:shadow-md",
      c.bg, c.border,
      highlight && value > 0 && "ring-2 ring-offset-1",
      highlight && value > 0 && color === "red" && "ring-red-300",
      highlight && value > 0 && color === "yellow" && "ring-yellow-300",
      highlight && value > 0 && color === "orange" && "ring-orange-300",
    )}>
      <div className="flex items-center justify-between mb-3">
        <span className={cls("rounded-lg p-2", c.badge)}>{icon}</span>
        {highlight && value > 0 && (
          <span className={cls("h-2.5 w-2.5 rounded-full animate-pulse", 
            color === "red" ? "bg-red-500" : color === "yellow" ? "bg-yellow-500" : "bg-orange-500"
          )} />
        )}
      </div>
      <p className={cls("text-3xl font-bold", c.text)}>
        <AnimatedNumber value={value} />
      </p>
      <p className={cls("text-xs font-semibold uppercase tracking-wide mt-1", c.text, "opacity-70")}>{label}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}

/* -- Vehicle table -------------------------------------------------- */

function SyncVehicleTable({ vehicles, filter }: { vehicles: InventoryComparisonVehicle[]; filter: string }) {
  const filtered = filter === "all" ? vehicles : vehicles.filter((v) => v.status === filter);
  const [showAll, setShowAll] = useState(false);
  const displayItems = showAll ? filtered : filtered.slice(0, 50);

  if (filtered.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-8 text-center">
        <p className="text-gray-400 text-sm">No vehicles match this filter.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-gray-200 shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50/80 border-b border-gray-200">
              <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Vehicle</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">VIN</th>
              <th className="px-4 py-3 text-right font-semibold text-gray-600 text-xs uppercase tracking-wider">Price</th>
            </tr>
          </thead>
          <tbody>
            {displayItems.map((v, i) => (
              <tr
                key={v.vin}
                className={cls(
                  "transition-colors hover:bg-gray-50",
                  i < displayItems.length - 1 && "border-b border-gray-100",
                  v.status === "missing_local" && "bg-red-50/40",
                  v.status === "missing_remote" && "bg-yellow-50/40",
                  v.status === "changed" && "bg-orange-50/40",
                )}
              >
                <td className="px-4 py-3">
                  <StatusBadge status={v.status} />
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900">
                    {v.year} {v.make} {v.model}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="font-mono text-xs text-gray-500 bg-gray-100 rounded px-2 py-0.5">
                    {v.vin}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-semibold text-gray-900">
                  {v.price || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > 50 && !showAll && (
        <div className="text-center">
          <button
            onClick={() => setShowAll(true)}
            className="text-sm text-brand-600 hover:text-brand-700 font-semibold"
          >
            Show all {filtered.length} vehicles
          </button>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { classes: string; label: string; icon: React.ReactNode }> = {
    match: {
      classes: "bg-green-100 text-green-700 border border-green-200",
      label: "In Sync",
      icon: <Icon d={icons.check} className="h-3.5 w-3.5 mr-1" sw={2.5} />,
    },
    missing_local: {
      classes: "bg-red-100 text-red-700 border border-red-200",
      label: "New on Site",
      icon: <Icon d={icons.plus} className="h-3.5 w-3.5 mr-1" sw={2.5} />,
    },
    missing_remote: {
      classes: "bg-yellow-100 text-yellow-700 border border-yellow-200",
      label: "Removed",
      icon: <Icon d={icons.minus} className="h-3.5 w-3.5 mr-1" sw={2.5} />,
    },
    changed: {
      classes: "bg-orange-100 text-orange-700 border border-orange-200",
      label: "Changed",
      icon: <Icon d={icons.refresh} className="h-3.5 w-3.5 mr-1" sw={2.5} />,
    },
  };
  const c = config[status] || config.match;
  return (
    <span className={cls("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold", c.classes)}>
      {c.icon}{c.label}
    </span>
  );
}

/* -- Animated progress ring ----------------------------------------- */

function ProgressRing({ progress, size = 120, stroke = 8 }: { progress: number; size?: number; stroke?: number }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;
  const color = progress >= 100 ? "#22c55e" : progress > 0 ? "#1e3a5f" : "#d1d5db";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={color} strokeWidth={stroke}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-bold text-gray-800">{progress}%</span>
      </div>
    </div>
  );
}

/* -- Sync scanning animation ---------------------------------------- */

function SyncScanProgress({ syncProgress }: { syncProgress: SyncProgress | null }) {
  const pg = syncProgress?.current_page || 0;
  const found = syncProgress?.vehicles_found || 0;
  const totalEst = syncProgress?.total_pages_estimate || 0;
  const status = syncProgress?.status || "starting";
  const message = syncProgress?.message || "Initializing...";

  // Compute a rough percentage
  let pct = 0;
  if (status === "starting") pct = 2;
  else if (status === "comparing") pct = 95;
  else if (totalEst > 0) pct = Math.min(90, Math.round((pg / totalEst) * 90));
  else if (pg > 0) pct = Math.min(80, pg * 2);

  return (
    <div className="card overflow-hidden">
      {/* Animated gradient header */}
      <div className="relative bg-gradient-to-r from-brand-600 via-brand-500 to-indigo-600 px-8 py-6 overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.1)_50%,transparent_75%)] bg-[length:250%_250%] animate-[shimmer_3s_linear_infinite]" />
        </div>
        <div className="relative flex items-center gap-4">
          <div className="relative">
            <div className="h-14 w-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Icon d={icons.signal} className="h-7 w-7 text-white" />
            </div>
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500 border-2 border-white" />
            </span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">
              {status === "comparing" ? "Comparing Inventory..." : "Scanning Live Website..."}
            </h2>
            <p className="text-white/70 text-sm mt-0.5">
              {status === "comparing"
                ? "Matching vehicles between website and your database"
                : "Fetching vehicle listings from Automotive Avenues NJ"
              }
            </p>
          </div>
        </div>
      </div>

      <div className="px-8 py-6 space-y-6">
        {/* Live stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl bg-brand-50 border border-brand-200 p-4 text-center">
            <p className="text-xs font-semibold text-brand-600 uppercase tracking-wider">Page</p>
            <p className="text-3xl font-bold text-brand-700 mt-1">{pg}</p>
            {totalEst > 0 && <p className="text-xs text-brand-500 mt-0.5">of ~{totalEst}</p>}
          </div>
          <div className="rounded-xl bg-green-50 border border-green-200 p-4 text-center">
            <p className="text-xs font-semibold text-green-600 uppercase tracking-wider">Vehicles Found</p>
            <p className="text-3xl font-bold text-green-700 mt-1">
              <AnimatedNumber value={found} />
            </p>
          </div>
          <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-center">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Progress</p>
            <p className="text-3xl font-bold text-gray-700 mt-1">{pct}%</p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500 transition-all duration-700 relative"
              style={{ width: `${Math.max(pct, 3)}%` }}
            >
              <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.3),transparent)] animate-[shimmer_2s_linear_infinite] bg-[length:200%_100%]" />
            </div>
          </div>
          <p className="text-sm text-gray-600 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
            {message}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   MAIN COMPONENT
   ================================================================ */

export default function Scrape() {
  /* -- State -------------------------------------------------------- */
  const [step, setStep] = useState(0);  // 0 = ready, 1 = sync running/done, 2 = scraping
  const [pages, setPages] = useState<number>(0);

  // Step 1: Sync check
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<InventoryComparison | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [vehicleFilter, setVehicleFilter] = useState("all");
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null);
  const syncPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Step 2: Scrape
  const [taskId, setTaskId] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [progress, setProgress] = useState<ScrapeProgress | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Monitor config
  const [monitor, setMonitor] = useState<MonitorConfig | null>(null);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [monitorInterval, setMonitorInterval] = useState(30);
  const [monitorPages, setMonitorPages] = useState(0);

  // Scrape logs
  const logsFetcher = useCallback(() => fetchScrapeLogs(1, 10), []);
  const { data: logs, refetch: refetchLogs } = useFetch<ScrapeLogList>(logsFetcher);

  // Load monitor config on mount
  useEffect(() => {
    fetchScrapeStatus().then((p) => setProgress(p)).catch(() => {});
    fetchMonitorConfig()
      .then((c) => {
        setMonitor(c);
        setMonitorInterval(c.interval_minutes);
        setMonitorPages(c.pages_to_scrape);
      })
      .catch(() => {});
  }, []);

  // Poll sync progress while syncing
  useEffect(() => {
    if (!syncing) {
      if (syncPollRef.current) {
        clearInterval(syncPollRef.current);
        syncPollRef.current = null;
      }
      return;
    }
    const poll = async () => {
      try {
        const p = await fetchSyncProgress();
        setSyncProgress(p);
      } catch {}
    };
    poll();
    syncPollRef.current = setInterval(poll, 1500);
    return () => {
      if (syncPollRef.current) {
        clearInterval(syncPollRef.current);
        syncPollRef.current = null;
      }
    };
  }, [syncing]);

  // Poll scrape progress
  useEffect(() => {
    if (!taskId) return;
    const poll = async () => {
      try {
        const p = await fetchScrapeStatus(taskId);
        setProgress(p);
        if (p.status === "completed" || p.status === "failed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          refetchLogs();
        }
      } catch {}
    };
    poll();
    pollRef.current = setInterval(poll, 2000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [taskId]); // eslint-disable-line react-hooks/exhaustive-deps

  const isRunning = progress?.status === "running";
  const scrapeCompleted = progress?.status === "completed";
  const scrapeFailed = progress?.status === "failed";

  /* -- Handlers ------------------------------------------------------ */

  async function handleSyncCheck() {
    setSyncing(true);
    setSyncError(null);
    setSyncResult(null);
    setSyncProgress(null);
    setStep(1);
    try {
      const data = await fetchInventoryComparison(pages);
      setSyncResult(data);
      const updatedConfig = await fetchMonitorConfig();
      setMonitor(updatedConfig);
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || "Sync check failed";
      setSyncError(msg);
    } finally {
      setSyncing(false);
      setSyncProgress(null);
    }
  }

  async function handleStartScrape() {
    setStep(2);
    try {
      setTriggering(true);
      setTriggerError(null);
      const result = await triggerScrape(pages);
      setTaskId(result.task_id);
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || "Failed to start scrape";
      setTriggerError(msg);
    } finally {
      setTriggering(false);
    }
  }

  function handleReset() {
    setStep(0);
    setSyncResult(null);
    setSyncError(null);
    setSyncProgress(null);
    setTaskId(null);
    setTriggerError(null);
    setProgress(null);
    setVehicleFilter("all");
  }

  async function handleMonitorToggle() {
    if (!monitor) return;
    setMonitorLoading(true);
    try {
      const updated = await updateMonitorConfig({
        enabled: !monitor.enabled,
        interval_minutes: monitorInterval,
        pages_to_scrape: monitorPages,
      });
      setMonitor(updated);
    } catch {}
    setMonitorLoading(false);
  }

  async function handleMonitorSave() {
    setMonitorLoading(true);
    try {
      const updated = await updateMonitorConfig({
        interval_minutes: monitorInterval,
        pages_to_scrape: monitorPages,
      });
      setMonitor(updated);
    } catch {}
    setMonitorLoading(false);
  }

  /* -- Derived ------------------------------------------------------- */

  const needsScrape = syncResult
    ? syncResult.missing_locally > 0 || syncResult.extra_locally > 0 || syncResult.changed > 0
    : false;
  const allInSync = syncResult ? !needsScrape : false;

  const filterCounts = syncResult ? {
    all: syncResult.vehicles.length,
    match: syncResult.vehicles.filter((v) => v.status === "match").length,
    missing_local: syncResult.vehicles.filter((v) => v.status === "missing_local").length,
    missing_remote: syncResult.vehicles.filter((v) => v.status === "missing_remote").length,
    changed: syncResult.vehicles.filter((v) => v.status === "changed").length,
  } : null;

  const stepperSteps = [
    { label: "Inventory Sync", sub: "Compare live site vs DB" },
    { label: "Review & Scrape", sub: "See changes, then scrape" },
    { label: "Complete", sub: "Database updated" },
  ];
  const stepperCurrent = step === 0 ? 0 : step === 1 ? (syncResult && !syncing ? 1 : 0) : 2;

  /* -- Render -------------------------------------------------------- */

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white shadow-lg shadow-brand-200">
              <Icon d={icons.bolt} />
            </div>
            Scrape Control Center
          </h1>
          <p className="mt-1 text-sm text-gray-500 ml-[52px]">
            Sync, compare, and scrape vehicle inventory from Automotive Avenues NJ
          </p>
        </div>
        {step > 0 && (
          <button onClick={handleReset} className="btn-secondary text-sm gap-2">
            <Icon d={icons.refresh} className="h-4 w-4" />
            Start Over
          </button>
        )}
      </div>

      {/* Step Indicator */}
      <StepIndicator steps={stepperSteps} current={stepperCurrent} />

      {/* ═══════ STEP 0 — Ready / Configuration ═══════ */}
      {step === 0 && (
        <div className="card overflow-hidden">
          <div className="bg-gradient-to-r from-brand-600 to-brand-700 px-8 py-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-3">
              <Icon d={icons.sync} className="h-6 w-6 text-white/80" />
              Step 1: Inventory Sync Check
            </h2>
            <p className="mt-2 text-white/70 text-sm max-w-2xl">
              First, we'll compare the live website inventory with your local database using a real browser.
              This identifies new vehicles, removed listings, and price changes — so you know exactly what needs updating.
            </p>
          </div>

          <div className="px-8 py-6 space-y-6">
            <div className="flex flex-wrap items-end gap-6">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wider">
                  Pages to Check
                </label>
                <select
                  value={pages}
                  onChange={(e) => setPages(Number(e.target.value))}
                  className="rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm font-medium focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition-all min-w-[180px]"
                >
                  <option value={0}>All Pages (~74 pages)</option>
                  <option value={1}>Page 1 Only (fastest)</option>
                  <option value={2}>First 2 Pages</option>
                  <option value={3}>First 3 Pages</option>
                  <option value={5}>First 5 Pages</option>
                  <option value={10}>First 10 Pages</option>
                  <option value={20}>First 20 Pages</option>
                </select>
              </div>

              <button
                onClick={handleSyncCheck}
                disabled={syncing}
                className="btn-primary text-base px-8 py-3 gap-2"
              >
                {syncing ? (
                  <><Spinner size="sm" /><span>Scanning...</span></>
                ) : (
                  <>
                    <Icon d={icons.search} />
                    Start Sync Check
                  </>
                )}
              </button>
            </div>

            {/* How it works */}
            <div className="rounded-xl bg-gray-50 border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">How it works</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  { n: 1, color: "blue", title: "Scan Website", desc: "Launch a browser to fetch all vehicle listings from the live site" },
                  { n: 2, color: "purple", title: "Compare Data", desc: "Match VINs and prices against your local database" },
                  { n: 3, color: "green", title: "Review Results", desc: "See what's new, changed, or removed before scraping" },
                ].map(({ n, color, title, desc }) => (
                  <div key={n} className="flex gap-3">
                    <div className={cls(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold",
                      color === "blue" ? "bg-blue-100 text-blue-600" :
                      color === "purple" ? "bg-purple-100 text-purple-600" :
                      "bg-green-100 text-green-600",
                    )}>{n}</div>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══════ STEP 1 — Sync Results ═══════ */}
      {step === 1 && (
        <>
          {/* Loading state with real-time progress */}
          {syncing && <SyncScanProgress syncProgress={syncProgress} />}

          {/* Error state */}
          {syncError && (
            <div className="card border-red-200 bg-red-50 p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
                  <Icon d={icons.error} className="h-5 w-5 text-red-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-red-800">Sync Check Failed</h3>
                  <p className="text-sm text-red-700 mt-1">{syncError}</p>
                  <button onClick={handleReset} className="mt-3 btn-secondary text-sm">
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Results */}
          {syncResult && !syncing && (
            <div className="space-y-6 animate-in">
              {/* Summary banner */}
              {allInSync ? (
                <div className="card border-green-200 bg-gradient-to-r from-green-50 to-emerald-50 p-6">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-green-100">
                      <Icon d={icons.checkBadge} className="h-8 w-8 text-green-600" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-green-800">Inventory is 100% In Sync!</h3>
                      <p className="text-sm text-green-600 mt-0.5">
                        All {syncResult.matched} vehicles match between the website and your database. No scrape needed.
                      </p>
                    </div>
                    <div className="flex gap-3 shrink-0">
                      <button onClick={handleReset} className="btn-secondary text-sm">Done</button>
                      <button onClick={handleStartScrape} className="btn-primary text-sm gap-2">
                        <Icon d={icons.bolt} className="h-4 w-4" />
                        Scrape Anyway
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="card border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50 p-6">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-orange-100">
                      <Icon d={icons.warning} className="h-8 w-8 text-orange-600" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-orange-800">Changes Detected!</h3>
                      <p className="text-sm text-orange-600 mt-0.5">
                        {syncResult.missing_locally > 0 && `${syncResult.missing_locally} new vehicle${syncResult.missing_locally > 1 ? "s" : ""} on site. `}
                        {syncResult.extra_locally > 0 && `${syncResult.extra_locally} removed from site. `}
                        {syncResult.changed > 0 && `${syncResult.changed} price change${syncResult.changed > 1 ? "s" : ""} detected. `}
                        Scrape to update your database.
                      </p>
                    </div>
                    <div className="shrink-0">
                      <button onClick={handleStartScrape} className="btn-primary text-base px-6 py-3 gap-2">
                        <Icon d={icons.bolt} />
                        Start Scrape
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <SyncCard label="Website" value={syncResult.website_count} color="blue" subtitle="Live listings"
                  icon={<Icon d={icons.globe} />} />
                <SyncCard label="Local DB" value={syncResult.local_count} color="purple" subtitle="Active vehicles"
                  icon={<Icon d={icons.database} />} />
                <SyncCard label="Matched" value={syncResult.matched} color="green" subtitle="In sync"
                  icon={<Icon d={icons.check} />} />
                <SyncCard label="New on Site" value={syncResult.missing_locally} color="red" subtitle="Not in your DB"
                  icon={<Icon d={icons.plus} />} highlight />
                <SyncCard label="Removed" value={syncResult.extra_locally} color="yellow" subtitle="No longer listed"
                  icon={<Icon d={icons.minus} />} highlight />
                <SyncCard label="Changed" value={syncResult.changed} color="orange" subtitle="Price changes"
                  icon={<Icon d={icons.refresh} />} highlight />
              </div>

              {/* Vehicle Filter Tabs + Table */}
              {filterCounts && (
                <div className="card overflow-hidden">
                  <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-900">Vehicle Details</h3>
                    <p className="text-xs text-gray-400">
                      Checked at {fmtDate(syncResult.checked_at)} &mdash; {syncResult.pages_checked >= 99 ? "all" : syncResult.pages_checked} page(s)
                    </p>
                  </div>

                  <div className="border-b border-gray-200 px-6 flex gap-1 overflow-x-auto">
                    {([
                      { key: "all", label: "All", count: filterCounts.all },
                      { key: "match", label: "In Sync", count: filterCounts.match },
                      { key: "missing_local", label: "New on Site", count: filterCounts.missing_local },
                      { key: "missing_remote", label: "Removed", count: filterCounts.missing_remote },
                      { key: "changed", label: "Changed", count: filterCounts.changed },
                    ] as const).map(({ key, label, count }) => (
                      <button
                        key={key}
                        onClick={() => setVehicleFilter(key)}
                        className={cls(
                          "px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                          vehicleFilter === key
                            ? "border-brand-600 text-brand-700"
                            : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
                        )}
                      >
                        {label}
                        <span className={cls(
                          "ml-2 inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs",
                          vehicleFilter === key ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-500",
                        )}>
                          {count}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="p-6">
                    <SyncVehicleTable vehicles={syncResult.vehicles} filter={vehicleFilter} />
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ═══════ STEP 2 — Scraping Progress ═══════ */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="card overflow-hidden">
            <div className={cls(
              "px-8 py-6",
              scrapeCompleted ? "bg-gradient-to-r from-green-500 to-emerald-600" :
              scrapeFailed ? "bg-gradient-to-r from-red-500 to-rose-600" :
              "bg-gradient-to-r from-brand-600 to-brand-700",
            )}>
              <h2 className="text-xl font-bold text-white flex items-center gap-3">
                {scrapeCompleted ? (
                  <Icon d={icons.check} className="h-6 w-6" />
                ) : scrapeFailed ? (
                  <Icon d={icons.x} className="h-6 w-6" />
                ) : (
                  <Spinner size="sm" />
                )}
                {scrapeCompleted ? "Scrape Complete!" : scrapeFailed ? "Scrape Failed" : "Step 2: Scraping in Progress..."}
              </h2>
              <p className="text-white/70 text-sm mt-1">
                {scrapeCompleted
                  ? "All vehicles have been updated in your database."
                  : scrapeFailed
                  ? "An error occurred during the scrape. Check logs for details."
                  : "Fetching vehicle data, downloading photos, and updating your database..."}
              </p>
            </div>

            <div className="px-8 py-8">
              {triggerError && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-red-700 text-sm mb-6">
                  {triggerError}
                </div>
              )}

              {progress && progress.status !== "idle" && (
                <div className="space-y-6">
                  <div className="flex flex-col sm:flex-row items-center gap-8">
                    <ProgressRing progress={progress.progress} />
                    <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 w-full">
                      <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-center">
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Found</p>
                        <p className="text-3xl font-bold text-gray-900 mt-1">
                          <AnimatedNumber value={progress.vehicles_found} />
                        </p>
                      </div>
                      <div className="rounded-xl bg-green-50 border border-green-200 p-4 text-center">
                        <p className="text-xs font-semibold text-green-600 uppercase tracking-wider">New</p>
                        <p className="text-3xl font-bold text-green-700 mt-1">
                          <AnimatedNumber value={progress.vehicles_new} />
                        </p>
                      </div>
                      <div className="rounded-xl bg-blue-50 border border-blue-200 p-4 text-center">
                        <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider">Updated</p>
                        <p className="text-3xl font-bold text-blue-700 mt-1">
                          <AnimatedNumber value={progress.vehicles_updated} />
                        </p>
                      </div>
                      <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-center">
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Page</p>
                        <p className="text-3xl font-bold text-gray-900 mt-1">
                          {progress.current_page}/{progress.total_pages || "?"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-gray-700">
                        Status:{" "}
                        <span className={
                          progress.status === "completed" ? "text-green-600" :
                          progress.status === "failed" ? "text-red-600" : "text-brand-600"
                        }>
                          {progress.status.charAt(0).toUpperCase() + progress.status.slice(1)}
                        </span>
                      </span>
                      {taskId && (
                        <span className="text-xs text-gray-400 font-mono">Task: {taskId}</span>
                      )}
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
                      <div
                        className={cls(
                          "h-full rounded-full transition-all duration-500",
                          progress.status === "completed" ? "bg-green-500" :
                          progress.status === "failed" ? "bg-red-500" : "bg-brand-600",
                        )}
                        style={{ width: `${progress.progress}%` }}
                      />
                    </div>
                    <p className="text-sm text-gray-600">
                      {progress.message.length > 200 ? progress.message.slice(0, 200) + "..." : progress.message}
                    </p>
                  </div>
                </div>
              )}

              {(scrapeCompleted || scrapeFailed) && (
                <div className="flex gap-3 mt-6 pt-6 border-t border-gray-200">
                  <button onClick={handleReset} className="btn-primary gap-2">
                    <Icon d={icons.refresh} className="h-4 w-4" />
                    New Sync Check
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════ 24/7 AUTO-MONITOR — Always visible ═══════ */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-100 text-purple-600">
              <Icon d={icons.clock} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">24/7 Auto-Monitor</h2>
              <p className="text-xs text-gray-500">Automatically checks and scrapes on a schedule</p>
            </div>
          </div>
          {monitor && (
            <span className={cls(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold",
              monitor.enabled
                ? "bg-green-100 text-green-700 border border-green-200"
                : "bg-gray-100 text-gray-500 border border-gray-200",
            )}>
              <span className={cls(
                "h-2 w-2 rounded-full",
                monitor.enabled ? "bg-green-500 animate-pulse" : "bg-gray-400",
              )} />
              {monitor.enabled ? "ACTIVE" : "OFF"}
            </span>
          )}
        </div>

        <div className="px-6 py-5 space-y-5">
          {monitor ? (
            <>
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wider">Check Interval</label>
                  <select
                    value={monitorInterval}
                    onChange={(e) => setMonitorInterval(Number(e.target.value))}
                    className="rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                  >
                    <option value={5}>5 min</option>
                    <option value={10}>10 min</option>
                    <option value={15}>15 min</option>
                    <option value={30}>30 min</option>
                    <option value={60}>1 hour</option>
                    <option value={120}>2 hours</option>
                    <option value={360}>6 hours</option>
                    <option value={720}>12 hours</option>
                    <option value={1440}>24 hours</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wider">Pages to Monitor</label>
                  <select
                    value={monitorPages}
                    onChange={(e) => setMonitorPages(Number(e.target.value))}
                    className="rounded-xl border border-gray-300 bg-white px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                  >
                    <option value={0}>All Pages</option>
                    <option value={1}>Page 1 Only</option>
                    <option value={2}>First 2 Pages</option>
                    <option value={3}>First 3 Pages</option>
                    <option value={5}>First 5 Pages</option>
                  </select>
                </div>

                <button
                  onClick={handleMonitorSave}
                  disabled={monitorLoading}
                  className="btn-secondary text-sm"
                >
                  Save Settings
                </button>

                <button
                  onClick={handleMonitorToggle}
                  disabled={monitorLoading}
                  className={cls(
                    "rounded-xl px-5 py-2.5 text-sm font-semibold transition-all shadow-sm",
                    monitor.enabled
                      ? "bg-red-600 text-white hover:bg-red-700 shadow-red-100"
                      : "bg-green-600 text-white hover:bg-green-700 shadow-green-100",
                  )}
                >
                  {monitorLoading ? <Spinner size="sm" /> : monitor.enabled ? "Stop Monitor" : "Start Monitor"}
                </button>
              </div>

              {monitor.last_check_at && (
                <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 space-y-1">
                  <div className="flex items-center gap-2">
                    <Icon d={icons.clock} className="h-4 w-4 text-gray-400" />
                    <p className="text-sm font-medium text-gray-700">Last Check: {fmtDate(monitor.last_check_at)}</p>
                  </div>
                  {monitor.last_check_result && (
                    <p className="text-xs font-mono text-gray-500 pl-6">{monitor.last_check_result}</p>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <Spinner size="sm" /> Loading monitor config...
            </div>
          )}
        </div>
      </div>

      {/* ═══════ SCRAPE HISTORY — Always visible ═══════ */}
      <div className="card overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-100 text-gray-600">
              <Icon d={icons.clock} />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Scrape History</h2>
          </div>
          <button
            onClick={() => refetchLogs()}
            className="text-xs text-brand-600 hover:text-brand-700 font-semibold flex items-center gap-1"
          >
            <Icon d={icons.refresh} className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>

        {!logs || logs.items.length === 0 ? (
          <div className="p-8 text-center">
            <Icon d={icons.doc} className="mx-auto h-10 w-10 text-gray-300" sw={1.5} />
            <p className="mt-3 text-sm text-gray-500">No scrape history yet. Run your first sync check above.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-200">
                  <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Started</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Task</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600 text-xs uppercase tracking-wider">Found</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600 text-xs uppercase tracking-wider">New</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600 text-xs uppercase tracking-wider">Updated</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600 text-xs uppercase tracking-wider">Removed</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600 text-xs uppercase tracking-wider">Duration</th>
                </tr>
              </thead>
              <tbody>
                {logs.items.map((log, i) => {
                  const started = utcDate(log.started_at)!;
                  const finished = log.finished_at ? utcDate(log.finished_at) : null;
                  const duration = finished
                    ? `${Math.round((finished.getTime() - started.getTime()) / 1000)}s`
                    : "--";
                  const isAuto = log.task_id?.startsWith("auto-");

                  return (
                    <tr key={log.id} className={cls(
                      "transition-colors hover:bg-gray-50",
                      i < logs.items.length - 1 && "border-b border-gray-100",
                    )}>
                      <td className="px-4 py-3 text-gray-700 text-xs">
                        {started.toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {isAuto ? (
                          <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-700 border border-purple-200 px-2.5 py-0.5 text-xs font-semibold">
                            Auto
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 font-mono">
                            {log.task_id?.slice(0, 16) || "-"}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cls(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border",
                          log.status === "completed" ? "bg-green-100 text-green-700 border-green-200" :
                          log.status === "failed" ? "bg-red-100 text-red-700 border-red-200" :
                          "bg-blue-100 text-blue-700 border-blue-200",
                        )}>
                          {log.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-medium">{log.vehicles_found}</td>
                      <td className="px-4 py-3 text-right text-green-600 font-medium">{log.vehicles_new}</td>
                      <td className="px-4 py-3 text-right text-blue-600 font-medium">{log.vehicles_updated}</td>
                      <td className="px-4 py-3 text-right text-red-600 font-medium">{log.vehicles_removed}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs font-mono">{duration}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
