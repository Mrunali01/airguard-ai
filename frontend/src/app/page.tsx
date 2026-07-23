"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";

type Primitive = string | number | boolean | null | undefined;

type MetricResult = {
  mae?: number;
  rmse?: number;
  r2?: number;
  aqi_category_accuracy?: number;
  rmse_improvement_vs_persistence?: number;
  type?: string;
};

type Action = {
  action?: string;
  priority?: string;
  why?: string[];
  human_review_required?: boolean;
};

type CommandEndpoint =
  | "request-verification"
  | "approve-intervention"
  | "reject-intervention"
  | "dispatch-intervention"
  | "start-intervention"
  | "complete-intervention"
  | "record-outcome"
  | "approve-advisory"
  | "regenerate-advisory"
  | "export-memo";

type CommandAck = {
  status?: string;
  action_type?: string;
  message?: string;
  workflow?: InterventionWorkflow;
  workflows?: Record<string, InterventionWorkflow>;
};

type InterventionStatus =
  | "Proposed"
  | "Under verification"
  | "Approved"
  | "Dispatched"
  | "In progress"
  | "Completed"
  | "Outcome recorded"
  | "Rejected";

type VerificationKey = "photo" | "evidence" | "engineer";

type InterventionWorkflow = {
  status: InterventionStatus;
  checks: Record<VerificationKey, boolean>;
};

type AirGuardPayload = {
  generated_at?: string;
  city?: string;
  data_mode?: string;
  station_location_id?: string | number;
  refresh_metadata?: {
    status?: "updated" | "cached" | "fallback";
    source_status?: "live" | "cached_fallback";
    fallback_type?: string;
    requested_at?: string;
    source_timestamp?: string;
    weather_timestamp?: string;
    source_age_hours?: number;
    freshness_status?: string;
    is_fresh?: boolean;
    new_reading_available?: boolean;
    served_from_cache?: boolean;
    cache_ttl_seconds?: number;
    error?: string;
  };
  analysis_metadata?: {
    analysis_id?: string;
    analysis_type?: string;
    analyzed_at?: string;
    uses_live_station_data?: boolean;
    source_timestamp?: string;
    forecast_recomputed?: boolean;
    source_attribution_mode?: string;
    human_review_required?: boolean;
    groq_synthesis_completed?: boolean;
  };
  llm_metadata?: {
    status?: "completed" | "deterministic_fallback";
    provider?: string;
    model?: string | null;
    synthesized_at?: string;
    error?: string;
    guardrail?: {
      deterministic_fields_preserved?: boolean;
      deterministic_fallback_used?: boolean;
      repairs_applied?: string[];
      human_review_required?: boolean;
    };
  };
  executive_summary?: Record<string, Primitive>;
  evidence_stack?: {
    ground_sensor?: {
      latest_datetime_utc?: string;
      max_age_hours?: number;
      pollutants?: Record<string, Primitive>;
      weather?: Record<string, Primitive>;
      aqi_estimate?: Record<string, Primitive>;
      dispersion?: Record<string, Primitive>;
    };
    forecast_validation?: {
      best_overall?: string;
      best_learned_model?: string;
      important_warning?: string;
      results?: Record<string, MetricResult>;
    };
    cpcb_window_forecast_validation?: {
      best_overall?: string;
      best_learned_model?: string;
      results?: Record<string, MetricResult>;
      important_warning?: string;
    };
    remote_sensing?: {
      satellite_layer?: string;
      dataset_id?: string;
      collection_image_count?: number;
      relative_no2_signal?: string;
      station_no2_stats?: Record<string, Primitive>;
      city_no2_stats?: Record<string, Primitive>;
      caveats?: string[];
      does_not_prove?: string[];
    };
    geospatial_context?: Record<string, Primitive>;
    source_hypotheses?: Array<{
      source?: string;
      confidence?: string;
      evidence?: string[];
    }>;
    wind_sector_evidence?: {
      stations?: Array<{
        source_alignment?: Array<{
          source?: string;
          reason?: string[];
        }>;
      }>;
    };
  };
  agent_outputs?: {
    groq_supervisor_decision?: {
      decision_headline?: string;
      reasoning_summary?: string;
      selected_forecast_method?: string;
      key_evidence_used?: string[];
      human_review_required?: boolean;
      limitations?: string[];
    };
    citizen_advisory?: {
      advisory_level?: string;
      panic_level?: string;
      english_advisory?: string;
      hindi_advisory?: string;
      who_should_take_care?: string[];
      recommended_precautions?: string[];
      data_limitations?: string[];
    };
  };
  recommended_actions?: Action[];
  safe_claims?: string[];
  claims_to_avoid?: string[];
  limitations?: string[];
};

type Screen =
  | "overview"
  | "hotspot"
  | "interventions"
  | "agent"
  | "advisory"
  | "reports"
  | "data";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const FALLBACK = "Unavailable";

const CommandLeafletMap = dynamic(() => import("@/components/CommandLeafletMap"), {
  ssr: false,
  loading: () => (
    <div className="grid h-[620px] place-items-center rounded-xl border border-slate-200 bg-slate-100 text-sm font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
      Loading satellite map...
    </div>
  ),
});

const navItems: Array<{ id: Screen; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "hotspot", label: "Hotspots" },
  { id: "interventions", label: "Interventions" },
  { id: "agent", label: "Agent Runs" },
  { id: "advisory", label: "Advisories" },
  { id: "reports", label: "Reports" },
  { id: "data", label: "Data Sources" },
];

const statuses = [
  "Proposed",
  "Under verification",
  "Approved",
  "Dispatched",
  "In progress",
  "Completed",
  "Outcome recorded",
  "Rejected",
];

const verificationItems: Array<{ key: VerificationKey; label: string }> = [
  { key: "photo", label: "Field inspection photo" },
  { key: "evidence", label: "Evidence confirmation" },
  { key: "engineer", label: "Ward engineer approval" },
];

function defaultWorkflow(): InterventionWorkflow {
  return {
    status: "Proposed",
    checks: {
      photo: false,
      evidence: false,
      engineer: false,
    },
  };
}

function actionKey(action: Action, index: number) {
  return `${index}:${action.action ?? "intervention"}`;
}

function isVerified(workflow: InterventionWorkflow) {
  return Object.values(workflow.checks).every(Boolean);
}

async function fetchDashboardData() {
  const response = await fetch(`${API_BASE_URL}/api/airguard/live`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`AirGuard API returned ${response.status}`);
  }

  return (await response.json()) as AirGuardPayload;
}

async function refreshDashboardData() {
  const response = await fetch(`${API_BASE_URL}/api/airguard/live/refresh`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Live refresh API returned ${response.status}`);
  }

  return (await response.json()) as AirGuardPayload;
}

async function analyzeDashboardData() {
  const response = await fetch(`${API_BASE_URL}/api/airguard/live/agent`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Live analysis API returned ${response.status}`);
  }

  return (await response.json()) as AirGuardPayload;
}

async function postCommand(
  endpoint: CommandEndpoint,
  payload: { action: string; action_id?: string; station_id?: string | number; screen?: string; notes?: string },
) {
  const response = await fetch(`${API_BASE_URL}/api/airguard/commands/${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Command API returned ${response.status}`);
  }

  return (await response.json()) as CommandAck;
}

async function fetchWorkflows() {
  const response = await fetch(`${API_BASE_URL}/api/airguard/intervention-workflows`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Workflow API returned ${response.status}`);
  }

  const json = (await response.json()) as { workflows?: Record<string, InterventionWorkflow> };
  return json.workflows ?? {};
}

async function fetchWorkflowsSafely() {
  try {
    return await fetchWorkflows();
  } catch {
    return {};
  }
}

async function postVerification(payload: {
  action_id: string;
  action?: string;
  station_id?: string | number;
  check: VerificationKey;
  checked: boolean;
}) {
  const response = await fetch(`${API_BASE_URL}/api/airguard/intervention-workflows/verification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Workflow API returned ${response.status}`);
  }

  return (await response.json()) as CommandAck;
}

function formatValue(value: Primitive, suffix = "") {
  if (value === null || value === undefined || value === "") return FALLBACK;
  if (typeof value === "number") {
    const formatted = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
    return `${formatted}${suffix}`;
  }
  return `${String(value).replaceAll("_", " ")}${suffix}`;
}

function titleize(value?: Primitive) {
  if (value === null || value === undefined || value === "") return FALLBACK;
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace("Pm25", "PM2.5")
    .replace("Pm10", "PM10")
    .replace("No2", "NO2")
    .replace("So2", "SO2")
    .replace("Co", "CO")
    .replace("O3", "O3");
}

function formatDateTime(value?: string) {
  if (!value) return FALLBACK;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(date);
}

function ageLabel(value: string | undefined, now: number) {
  if (!value) return FALLBACK;
  const ageMs = now - new Date(value).getTime();
  if (!Number.isFinite(ageMs)) return FALLBACK;
  const hours = Math.max(0, ageMs / 36e5);
  if (hours < 48) return `${hours.toFixed(1)} hours`;
  return `${Math.floor(hours / 24)} days`;
}

function timestampIsStale(value: string | undefined, now: number) {
  if (!value) return true;
  const timestamp = new Date(value).getTime();
  return !Number.isFinite(timestamp) || now - timestamp > 24 * 36e5;
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700/80 dark:bg-[#111A2B] dark:shadow-black/20 ${className}`}>
      {children}
    </section>
  );
}

function SectionTitle({
  label,
  title,
  aside,
}: {
  label?: string;
  title: string;
  aside?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        {label ? (
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">
            {label}
          </p>
        ) : null}
        <h2 className="mt-1 text-lg font-semibold text-slate-950 dark:text-slate-50">{title}</h2>
      </div>
      {aside}
    </div>
  );
}

function StatCard({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: Primitive;
  detail?: Primitive;
  tone?: "neutral" | "teal" | "amber" | "red";
}) {
  const toneClass = {
    neutral: "border-slate-200 dark:border-slate-700 dark:bg-slate-900",
    teal: "border-teal-200 bg-teal-50 dark:border-teal-800 dark:bg-teal-950/40",
    amber: "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40",
    red: "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/40",
  };

  return (
    <div className={`min-w-0 rounded-xl border p-4 ${toneClass[tone]}`}>
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-2 break-words text-[clamp(1.35rem,2vw,1.75rem)] font-semibold leading-tight text-slate-950 dark:text-slate-50">
        {formatValue(value)}
      </p>
      {detail ? <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{formatValue(detail)}</p> : null}
    </div>
  );
}

function Pill({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: "slate" | "teal" | "amber" | "red" | "purple" | "green";
}) {
  const toneClass = {
    slate: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200",
    teal: "border-teal-200 bg-teal-50 text-teal-800 dark:border-teal-700 dark:bg-teal-950 dark:text-teal-200",
    amber: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200",
    red: "border-red-200 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200",
    purple: "border-purple-200 bg-purple-50 text-purple-800 dark:border-purple-700 dark:bg-purple-950 dark:text-purple-200",
    green: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
  };

  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClass[tone]}`}>
      {children}
    </span>
  );
}

function List({ items, empty = FALLBACK }: { items?: string[]; empty?: string }) {
  if (!items?.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm leading-6 text-slate-700 dark:text-slate-100">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="flex gap-2">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-700 dark:bg-teal-300" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function StationDrawer({
  open,
  onClose,
  data,
  now,
  onReport,
  onAgent,
  onCommand,
}: {
  open: boolean;
  onClose: () => void;
  data: AirGuardPayload | null;
  now: number;
  onReport: () => void;
  onAgent: () => void;
  onCommand: (endpoint: CommandEndpoint, action: string, notes?: string) => void;
}) {
  const summary = data?.executive_summary ?? {};
  const ground = data?.evidence_stack?.ground_sensor;

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-label="Close station profile"
        onClick={onClose}
        className="fixed inset-0 z-[1900] hidden bg-slate-950/45 backdrop-blur-[2px] lg:block"
      />
      <aside className="fixed inset-y-0 right-0 z-[2000] flex w-full max-w-[520px] flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-[#0B1220]">
        <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 p-5 backdrop-blur dark:border-slate-700 dark:bg-[#0B1220]/95">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700 dark:text-teal-300">Station profile</p>
              <h2 className="mt-1 break-words text-2xl font-semibold text-slate-950 dark:text-slate-50">
                Station {formatValue(data?.station_location_id)}
              </h2>
            </div>
            <button onClick={onClose} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200">
              Close
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
            <p className="text-sm text-slate-500 dark:text-slate-400">CPCB AQI</p>
            <p className="mt-1 break-words text-[clamp(1.8rem,4vw,2.75rem)] font-semibold leading-tight text-slate-950 dark:text-slate-50">
              {formatValue(summary.cpcb_aqi)} - {formatValue(summary.cpcb_aqi_category)}
            </p>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              Dominant pollutant: {titleize(summary.dominant_pollutant)}
            </p>
            <p className="text-sm text-amber-700 dark:text-amber-300">
              Sensor age: {ageLabel(ground?.latest_datetime_utc, now)} - {timestampIsStale(ground?.latest_datetime_utc, now) ? "STALE" : "FRESH"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {["pm25", "pm10", "co", "o3", "no2", "so2"].map((key) => (
              <StatCard key={key} label={titleize(key)} value={ground?.pollutants?.[key]} />
            ))}
          </div>
          <div className="rounded-xl border border-slate-200 p-4 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-200">
            <p>Wind: {formatValue(ground?.weather?.wind_speed)} m/s from {formatValue(summary.wind_from_sector)}</p>
            <p>Dispersion risk: {titleize(ground?.dispersion?.dispersion_risk)}</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              onClick={() => {
                onCommand("request-verification", "Open Intelligence Report", "Operator opened station intelligence report.");
                onReport();
              }}
              className="rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white dark:bg-slate-100 dark:text-slate-950"
            >
              Open Intelligence Report
            </button>
            <button
              onClick={() => {
                onCommand("request-verification", "Run Agent Analysis", "Operator requested station analysis from drawer.");
                onAgent();
              }}
              className="rounded-lg bg-teal-700 px-4 py-3 text-sm font-semibold text-white"
            >
              Run Agent Analysis
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export default function Home() {
  const [data, setData] = useState<AirGuardPayload | null>(null);
  const [screen, setScreen] = useState<Screen>("overview");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [commandStatus, setCommandStatus] = useState<string | null>(null);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [commandPending, setCommandPending] = useState<string | null>(null);
  const [workflows, setWorkflows] = useState<Record<string, InterventionWorkflow>>({});
  const [now, setNow] = useState(() => Date.now());

  const loadData = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    setRefreshStatus(null);
    try {
      const [dashboardData, workflowData] = await Promise.all([
        refreshDashboardData(),
        fetchWorkflowsSafely(),
      ]);
      setData(dashboardData);
      setWorkflows(workflowData);
      setNow(Date.now());

      const metadata = dashboardData.refresh_metadata;
      if (metadata?.status === "fallback") {
        setRefreshStatus(
          `Live services were unavailable. Showing ${metadata.fallback_type?.replaceAll("_", " ") ?? "cached data"}.`,
        );
      } else if (metadata?.new_reading_available) {
        setRefreshStatus(`New station reading loaded: ${formatDateTime(metadata.source_timestamp)}.`);
      } else if (metadata?.served_from_cache) {
        setRefreshStatus("Refresh checked. The five-minute live cache is still current.");
      } else {
        setRefreshStatus(`Live sources checked; no newer station reading is available yet.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load AirGuard data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchDashboardData(), fetchWorkflowsSafely()])
      .then(([dashboardData, workflowData]) => {
        if (active) {
          setData(dashboardData);
          setWorkflows(workflowData);
          setNow(Date.now());
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load AirGuard data");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadData();
    }, 10 * 60 * 1000);

    return () => window.clearInterval(interval);
  }, [loadData]);

  const runLiveAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    setCommandStatus(null);
    try {
      const analysis = await analyzeDashboardData();
      setData(analysis);
      setNow(Date.now());
      setScreen("agent");
      const analysisId = analysis.analysis_metadata?.analysis_id;
      const evidenceMode = analysis.analysis_metadata?.uses_live_station_data
        ? "live station evidence"
        : "cached fallback evidence";
      if (analysis.llm_metadata?.status === "completed") {
        setCommandStatus(
          `${analysisId ?? "Live analysis"} synthesized by Groq ${analysis.llm_metadata.model ?? "model"} using ${evidenceMode}. Deterministic guardrails preserved the operational facts.`,
        );
      } else {
        setCommandStatus(
          `${analysisId ?? "Live analysis"} completed using ${evidenceMode}. Groq was unavailable, so the deterministic fallback was used.`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Live analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const runCommand = useCallback(
    async (endpoint: CommandEndpoint, action: string, notes?: string, actionId?: string) => {
      setCommandPending(`${endpoint}:${action}`);
      setCommandStatus(null);
      try {
        const result = await postCommand(endpoint, {
          action,
          action_id: actionId,
          station_id: data?.station_location_id,
          screen,
          notes,
        });
        if (result.workflows) {
          setWorkflows(result.workflows);
        }
        setCommandStatus(result.message ?? `${titleize(endpoint)} accepted by backend.`);
        return true;
      } catch (err) {
        setCommandStatus(err instanceof Error ? err.message : "Command failed.");
        return false;
      } finally {
        setCommandPending(null);
      }
    },
    [data, screen],
  );

  const summary = useMemo(() => data?.executive_summary ?? {}, [data]);
  const evidence = useMemo(() => data?.evidence_stack ?? {}, [data]);
  const ground = evidence.ground_sensor;
  const geo = useMemo(() => evidence.geospatial_context ?? {}, [evidence]);
  const remote = evidence.remote_sensing;
  const forecast = evidence.cpcb_window_forecast_validation ?? evidence.forecast_validation;
  const supervisor = data?.agent_outputs?.groq_supervisor_decision;
  const advisory = data?.agent_outputs?.citizen_advisory;
  const actions = data?.recommended_actions ?? [];
  const sourceTime = ground?.latest_datetime_utc;
  const isRealPilot = Boolean(data?.station_location_id);
  const stale = timestampIsStale(sourceTime, now);
  const refreshMetadata = data?.refresh_metadata;
  const upstreamFallback = refreshMetadata?.source_status === "cached_fallback";

  const forecastResults = forecast?.results ?? {};
  const bestResult = forecast?.best_overall ? forecastResults[forecast.best_overall] : undefined;

  const toggleVerification = useCallback(
    async (key: string, action: Action, check: VerificationKey) => {
      const current = workflows[key] ?? defaultWorkflow();
      setCommandPending(`verification:${key}:${check}`);
      setCommandStatus(null);
      try {
        const result = await postVerification({
          action_id: key,
          action: action.action,
          station_id: data?.station_location_id,
          check,
          checked: !current.checks[check],
        });
        if (result.workflows) {
          setWorkflows(result.workflows);
        }
        setCommandStatus(result.message ?? "Verification checklist updated.");
      } catch (err) {
        setCommandStatus(err instanceof Error ? err.message : "Verification update failed.");
      } finally {
        setCommandPending(null);
      }
    },
    [data, workflows],
  );

  const transitionIntervention = useCallback(
    async (
      key: string,
      action: Action,
      endpoint: CommandEndpoint,
      notes: string,
    ) => {
      await runCommand(endpoint, action.action ?? endpoint, notes, key);
    },
    [runCommand],
  );

  const traceSteps = useMemo(
    () => [
      {
        name: "Sensor freshness check",
        result: stale ? "Data is stale" : "Data is fresh",
        evidence: [`Source reading: ${formatDateTime(sourceTime)}`, `Sensor age: ${ageLabel(sourceTime, now)}`],
        limitations: ["Freshness is based on the station timestamp supplied by the API."],
      },
      {
        name: "CPCB AQI calculator",
        result: `AQI ${formatValue(summary.cpcb_aqi)}, ${titleize(summary.dominant_pollutant)} dominant`,
        evidence: [`Category: ${formatValue(summary.cpcb_aqi_category)}`],
        limitations: ["Regulatory use still requires official CPCB averaging windows."],
      },
      {
        name: "Forecast validation",
        result: `${formatValue(forecast?.best_overall)} selected for CPCB-window forecast`,
        evidence: [`Best learned model: ${formatValue(forecast?.best_learned_model)}`],
        limitations: forecast?.important_warning ? [forecast.important_warning] : [],
      },
      {
        name: "Geospatial evidence",
        result: `Road density ${formatValue(geo.road_density_km_per_km2)} km/km2; ${formatValue(geo.industrial_poi_count)} industrial POIs`,
        evidence: [`Nearest major road: ${formatValue(geo.nearest_major_road_m)} m`],
        limitations: ["POI proximity is screening context, not causal proof."],
      },
      {
        name: "Satellite evidence",
        result: `${formatValue(remote?.relative_no2_signal)} from ${formatValue(remote?.collection_image_count)} images`,
        evidence: [`Layer: ${formatValue(remote?.satellite_layer)}`],
        limitations: remote?.caveats ?? [],
      },
      {
        name: "Evidence guardrail",
        result: `${formatValue(data?.safe_claims?.length)} supported claims; ${formatValue(data?.claims_to_avoid?.length)} overclaims blocked`,
        evidence: data?.safe_claims,
        limitations: data?.claims_to_avoid,
      },
      {
        name: "Supervisor",
        result: formatValue(supervisor?.decision_headline ?? summary.headline),
        evidence: supervisor?.key_evidence_used,
        limitations: supervisor?.limitations ?? data?.limitations,
      },
    ],
    [data, forecast, geo, now, remote, sourceTime, stale, summary, supervisor],
  );

  const topStats = [
    {
      label: "CPCB AQI",
      value: summary.cpcb_aqi ?? summary.current_estimated_aqi,
      detail: summary.cpcb_aqi_category ?? summary.current_estimated_aqi_category,
      tone: "teal" as const,
    },
    {
      label: "Dominant pollutant",
      value: titleize(summary.dominant_pollutant),
      detail: ground?.pollutants?.pm10 ? `${formatValue(ground.pollutants.pm10)} ug/m3` : undefined,
      tone: "neutral" as const,
    },
    {
      label: "24h forecast",
      value: summary.selected_forecast_method,
      detail: bestResult?.rmse ? `RMSE ${formatValue(bestResult.rmse)}` : forecast?.best_overall,
      tone: "neutral" as const,
    },
    {
      label: "Dispersion risk",
      value: titleize(ground?.dispersion?.dispersion_risk),
      detail: summary.wind_speed_class ? `${formatValue(summary.wind_speed_class)} wind` : undefined,
      tone: "amber" as const,
    },
    {
      label: "Monitoring priority",
      value: titleize(summary.monitoring_priority),
      detail: summary.intervention_required_now ? "Immediate review" : "Preventive action",
      tone: "amber" as const,
    },
  ];

  return (
    <main
      className={`min-h-screen ${
        theme === "dark" ? "dark bg-slate-950 text-slate-100" : "bg-[#F5F7FA] text-slate-900"
      }`}
    >
      <StationDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        data={data}
        now={now}
        onReport={() => {
          setDrawerOpen(false);
          setScreen("hotspot");
        }}
        onAgent={() => {
          setDrawerOpen(false);
          void runLiveAnalysis();
        }}
        onCommand={(endpoint, action, notes) => void runCommand(endpoint, action, notes)}
      />

      <div className="flex min-h-screen">
        <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-[#0B1628] p-5 text-white dark:border-slate-800 dark:bg-black lg:block">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-teal-300">AirGuard AI</p>
            <h1 className="mt-2 text-2xl font-semibold">Chennai Command Centre</h1>
          </div>
          <nav className="mt-8 space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setScreen(item.id)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm font-semibold transition ${
                  screen === item.id ? "bg-teal-600 text-white" : "text-slate-300 hover:bg-white/10"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="mt-8 rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
            <p className="font-semibold text-white">Workflow</p>
            <p className="mt-2 leading-6">
              Detect hotspot {"->"} understand cause {"->"} review evidence {"->"} approve action {"->"} communicate.
            </p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 md:px-6">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-xl font-semibold text-slate-950 dark:text-slate-50 lg:hidden">AirGuard AI</h1>
                <Pill tone={isRealPilot ? (stale ? "amber" : "green") : "purple"}>
                  {isRealPilot ? "REAL STATION PILOT" : "SYNTHETIC CITY DEMO"}
                </Pill>
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  {isRealPilot
                    ? `OpenAQ station ${formatValue(data?.station_location_id)}`
                    : "10 simulated Chennai wards"}
                </span>
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  Source reading: {formatDateTime(sourceTime)}
                </span>
                <Pill tone={error || upstreamFallback ? "red" : stale ? "amber" : "green"}>
                  {error
                    ? "PIPELINE FAILURE"
                    : upstreamFallback
                      ? "CACHED FALLBACK"
                      : stale
                        ? "STALE DATA"
                        : "FRESH DATA"}
                </Pill>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  {theme === "dark" ? "Light mode" : "Dark mode"}
                </button>
                <button
                  onClick={() => void loadData()}
                  disabled={refreshing}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  {refreshing ? "Refreshing..." : "Refresh"}
                </button>
                <button
                  onClick={() => void runLiveAnalysis()}
                  disabled={analyzing}
                  className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
                >
                  {analyzing ? "Running Groq agent..." : "Run Groq Analysis"}
                </button>
              </div>
            </div>
          </header>

          {loading ? (
            <div className="p-6">
              <Card className="p-6">
                <p className="text-sm font-bold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">Loading command centre</p>
                <div className="mt-6 grid gap-4 md:grid-cols-5">
                  {[0, 1, 2, 3, 4].map((item) => (
                    <div key={item} className="h-28 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
                  ))}
                </div>
              </Card>
            </div>
          ) : (
            <div className="p-4 md:p-6">
              {commandStatus ? (
                <Card className="mb-4 border-teal-200 bg-teal-50 p-4 dark:border-teal-800 dark:bg-teal-950/40">
                  <p className="text-sm font-semibold text-teal-900 dark:text-teal-100">{commandStatus}</p>
                </Card>
              ) : null}
              {refreshStatus ? (
                <Card className={`mb-4 p-4 ${upstreamFallback ? "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40" : "border-teal-200 bg-teal-50 dark:border-teal-800 dark:bg-teal-950/40"}`}>
                  <p className={`text-sm font-semibold ${upstreamFallback ? "text-amber-900 dark:text-amber-100" : "text-teal-900 dark:text-teal-100"}`}>
                    {refreshStatus}
                  </p>
                </Card>
              ) : null}
              {error ? (
                <Card className="mb-4 border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/40">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-red-800 dark:text-red-100">
                      API unavailable: {error}. The UI remains available, but live evidence cannot be refreshed.
                    </p>
                    <button onClick={() => void loadData()} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-semibold text-white">
                      Retry
                    </button>
                  </div>
                </Card>
              ) : null}

              {screen === "overview" ? (
                <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-5">
                    {topStats.map((item) => (
                      <StatCard key={item.label} {...item} />
                    ))}
                  </div>
                  <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
                    <Card className="p-4">
                      <SectionTitle
                        label="Command map"
                        title="Chennai hotspot and exposure layers"
                        aside={<Pill tone="teal">Map-first operations view</Pill>}
                      />
                      <CommandLeafletMap
                        category={summary.cpcb_aqi_category ?? summary.current_estimated_aqi_category}
                        stationId={data?.station_location_id}
                        onStationClick={() => setDrawerOpen(true)}
                      />
                    </Card>
                    <div className="space-y-4">
                      <Card className="p-4">
                        <SectionTitle label="Priority queue" title="Recommended next actions" />
                        <div className="space-y-3">
                          {actions.slice(0, 4).map((action, index) => (
                            <button
                              key={`${action.action}-${index}`}
                              onClick={() => setScreen("interventions")}
                              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-left hover:border-teal-300 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-teal-500"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <p className="font-semibold text-slate-950 dark:text-slate-50">{action.action ?? FALLBACK}</p>
                                <Pill tone="amber">{action.priority ?? FALLBACK}</Pill>
                              </div>
                              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                Human review required: {formatValue(action.human_review_required)}
                              </p>
                            </button>
                          ))}
                        </div>
                      </Card>
                      <Card className="p-4">
                        <SectionTitle label="Evidence summary" title="Why this needs review" />
                        <List items={supervisor?.key_evidence_used?.slice(0, 5)} />
                      </Card>
                    </div>
                  </div>
                  <Card className="p-4">
                    <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                      <span>AQI {formatValue(summary.cpcb_aqi ?? summary.current_estimated_aqi)}</span>
                      <span>|</span>
                      <span>{formatValue(summary.cpcb_aqi_category ?? summary.current_estimated_aqi_category)}</span>
                      <span>|</span>
                      <span>{titleize(summary.dominant_pollutant)} dominant</span>
                      <span>|</span>
                      <span>{formatValue(summary.wind_speed_class)} wind</span>
                      <span>|</span>
                      <span>{formatValue(geo.vulnerability_poi_count)} sensitive receptors</span>
                    </div>
                  </Card>
                </div>
              ) : null}

              {screen === "hotspot" ? (
                <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
                  <div className="space-y-4">
                    <Card className="p-5">
                      <SectionTitle label="Hotspot intelligence" title={`Station ${formatValue(data?.station_location_id)} drilldown`} />
                      <div className="grid gap-3 md:grid-cols-5">
                        <StatCard label="Current AQI" value={summary.cpcb_aqi ?? summary.current_estimated_aqi} detail={summary.cpcb_aqi_category ?? summary.current_estimated_aqi_category} tone="teal" />
                        <StatCard label="Forecast AQI" value={summary.selected_forecast_method} detail={forecast?.best_overall} />
                        <StatCard label="Uncertainty" value={bestResult?.rmse} detail="RMSE" tone="amber" />
                        <StatCard label="Threshold probability" value={FALLBACK} detail="Not supplied by API" />
                        <StatCard label="Data freshness" value={ageLabel(sourceTime, now)} detail={stale ? "STALE" : "Fresh"} tone={stale ? "amber" : "teal"} />
                      </div>
                    </Card>
                    <Card className="p-5">
                      <SectionTitle label="Why might it be happening?" title="Source hypotheses, not causal attribution" />
                      <div className="grid gap-4 md:grid-cols-2">
                        {(evidence.source_hypotheses ?? []).map((item, index) => (
                          <div key={`${item.source}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
                            <div className="flex items-start justify-between gap-3">
                              <h3 className="font-semibold uppercase text-slate-950 dark:text-slate-50">{item.source ?? FALLBACK}</h3>
                              <Pill tone="amber">{item.confidence ?? FALLBACK}</Pill>
                            </div>
                            <div className="mt-3">
                              <List items={item.evidence} />
                            </div>
                            <p className="mt-3 rounded-lg bg-white p-3 text-xs font-semibold text-slate-600 dark:bg-slate-950/70 dark:text-slate-300">
                              Important: plausible source hypothesis, not causal proof.
                            </p>
                          </div>
                        ))}
                      </div>
                    </Card>
                  </div>
                  <div className="space-y-4">
                    <Card className="p-5">
                      <SectionTitle label="Who is exposed?" title="Sensitive receptors within 1.5 km" />
                      <div className="grid gap-3">
                        <StatCard label="Schools" value={geo.school_poi_count} />
                        <StatCard label="Hospitals and clinics" value={geo.hospital_poi_count} />
                        <StatCard label="Total vulnerable POIs" value={geo.vulnerability_poi_count} tone="amber" />
                      </div>
                    </Card>
                    <Card className="p-5">
                      <SectionTitle label="What should the city do?" title="Ranked intervention path" />
                      <List items={actions.map((action) => action.action ?? FALLBACK)} />
                    </Card>
                  </div>
                </div>
              ) : null}

              {screen === "interventions" ? (
                <div className="space-y-4">
                  <Card className="p-5">
                    <SectionTitle label="Intervention queue" title="Human-approved municipal workflow" />
                    <div className="flex flex-wrap gap-2">
                      {statuses.map((status) => {
                        const count = actions.filter((action, index) => {
                          const workflow = workflows[actionKey(action, index)] ?? defaultWorkflow();
                          return workflow.status === status;
                        }).length;

                        return (
                          <Pill key={status} tone={count ? "amber" : "slate"}>
                            {status}{count ? ` (${count})` : ""}
                          </Pill>
                        );
                      })}
                    </div>
                  </Card>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {actions.map((action, index) => {
                      const key = actionKey(action, index);
                      const workflow = workflows[key] ?? defaultWorkflow();
                      const verified = isVerified(workflow);
                      const canRequestVerification = workflow.status === "Proposed";
                      const canApprove =
                        verified &&
                        (workflow.status === "Proposed" ||
                          workflow.status === "Under verification");
                      const canDispatch = workflow.status === "Approved";
                      const canStart = workflow.status === "Dispatched";
                      const canComplete = workflow.status === "In progress";
                      const canRecordOutcome = workflow.status === "Completed";
                      const terminal = workflow.status === "Rejected" || workflow.status === "Outcome recorded";

                      return (
                      <Card key={key} className="p-5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill tone="amber">{titleize(action.priority)} priority</Pill>
                          <Pill tone={workflow.status === "Rejected" ? "red" : workflow.status === "Outcome recorded" ? "green" : "teal"}>
                            {workflow.status}
                          </Pill>
                        </div>
                        <h3 className="mt-3 text-xl font-semibold text-slate-950 dark:text-slate-50">{action.action ?? FALLBACK}</h3>
                        <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
                          Department: {index === 0 ? "Municipal Operations" : index === 1 ? "Traffic Police" : "Ward Response Cell"}
                        </p>
                        <div className="mt-4">
                          <p className="mb-2 text-sm font-semibold text-slate-950 dark:text-slate-100">Why recommended</p>
                          <List items={action.why} />
                        </div>
                        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950/50">
                          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">Required before approval</p>
                            <Pill tone={verified ? "green" : "amber"}>{verified ? "Verified" : "Verification pending"}</Pill>
                          </div>
                          {verificationItems.map((item) => (
                            <label key={item.key} className="mb-2 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                              <input
                                checked={workflow.checks[item.key]}
                                disabled={terminal || workflow.status === "Approved" || workflow.status === "Dispatched" || workflow.status === "In progress" || workflow.status === "Completed"}
                                onChange={() => void toggleVerification(key, action, item.key)}
                                type="checkbox"
                                className="accent-teal-700 disabled:cursor-not-allowed dark:accent-teal-400"
                              />
                              {item.label}
                            </label>
                          ))}
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            disabled={terminal}
                            onClick={() => void transitionIntervention(key, action, "reject-intervention", "Operator rejected this proposed intervention.")}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-45 dark:border-slate-700 dark:text-slate-200"
                          >
                            {commandPending === `reject-intervention:${action.action ?? "Reject intervention"}` ? "Rejecting..." : "Reject"}
                          </button>
                          <button
                            disabled={!canRequestVerification}
                            onClick={() => void transitionIntervention(key, action, "request-verification", "Operator requested field verification before dispatch.")}
                            className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800 disabled:cursor-not-allowed disabled:opacity-45 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
                          >
                            {commandPending === `request-verification:${action.action ?? "Request verification"}` ? "Requesting..." : "Request Verification"}
                          </button>
                          <button
                            disabled={!canApprove}
                            onClick={() => void transitionIntervention(key, action, "approve-intervention", "Human operator approved this intervention for municipal workflow.")}
                            className="rounded-lg bg-teal-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
                          >
                            {commandPending === `approve-intervention:${action.action ?? "Approve intervention"}` ? "Approving..." : "Approve Intervention"}
                          </button>
                          <button
                            disabled={!canDispatch}
                            onClick={() => void transitionIntervention(key, action, "dispatch-intervention", "Approved intervention dispatched to responsible department.")}
                            className="rounded-lg border border-teal-300 px-3 py-2 text-sm font-semibold text-teal-800 disabled:cursor-not-allowed disabled:opacity-45 dark:border-teal-700 dark:text-teal-200"
                          >
                            Dispatch
                          </button>
                          <button
                            disabled={!canStart}
                            onClick={() => void transitionIntervention(key, action, "start-intervention", "Field team marked intervention as in progress.")}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-45 dark:border-slate-700 dark:text-slate-200"
                          >
                            Start
                          </button>
                          <button
                            disabled={!canComplete}
                            onClick={() => void transitionIntervention(key, action, "complete-intervention", "Field team marked intervention as completed.")}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-45 dark:border-slate-700 dark:text-slate-200"
                          >
                            Complete
                          </button>
                          <button
                            disabled={!canRecordOutcome}
                            onClick={() => void transitionIntervention(key, action, "record-outcome", "Operator recorded post-intervention outcome.")}
                            className="rounded-lg border border-emerald-300 px-3 py-2 text-sm font-semibold text-emerald-800 disabled:cursor-not-allowed disabled:opacity-45 dark:border-emerald-700 dark:text-emerald-200"
                          >
                            Record Outcome
                          </button>
                        </div>
                        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                          AI recommendation is advisory only. Municipal approval remains a human operator action. Human review required: {formatValue(action.human_review_required)}
                        </p>
                      </Card>
                    );
                    })}
                  </div>
                </div>
              ) : null}

              {screen === "agent" ? (
                <Card className="p-5">
                  <SectionTitle
                    label="Analysis trace"
                    title={`Analysis Run ${data?.analysis_metadata?.analysis_id ?? `AG-${String(data?.station_location_id ?? "001").padStart(3, "0")}`}`}
                    aside={<Pill tone="teal">Trace, not chain-of-thought</Pill>}
                  />
                  {data?.analysis_metadata ? (
                    <div className="mb-4 flex flex-wrap gap-2">
                      <Pill tone={data.analysis_metadata.uses_live_station_data ? "green" : "amber"}>
                        {data.analysis_metadata.uses_live_station_data ? "LIVE EVIDENCE" : "CACHED EVIDENCE"}
                      </Pill>
                      <Pill tone="slate">
                        {data.analysis_metadata.forecast_recomputed ? "LIVE FORECAST" : "HISTORICAL FORECAST CONTEXT"}
                      </Pill>
                      <Pill tone={data.llm_metadata?.status === "completed" ? "teal" : "amber"}>
                        {data.llm_metadata?.status === "completed"
                          ? `GROQ ${data.llm_metadata.model ?? "SYNTHESIS"}`
                          : "DETERMINISTIC FALLBACK"}
                      </Pill>
                      <span className="text-sm text-slate-500 dark:text-slate-400">
                        Analyzed: {formatDateTime(data.analysis_metadata.analyzed_at)}
                      </span>
                    </div>
                  ) : null}
                  <div className="space-y-3">
                    {traceSteps.map((step, index) => (
                      <details key={step.name} open={index < 2} className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
                        <summary className="cursor-pointer font-semibold text-slate-950 dark:text-slate-50">
                          Check {index + 1}: {step.name}
                          <span className="ml-3 text-sm font-normal text-slate-600 dark:text-slate-300">Result: {step.result}</span>
                        </summary>
                        <div className="mt-4 grid gap-4 md:grid-cols-4">
                          <div>
                            <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Tool input</p>
                            <p className="text-sm text-slate-700 dark:text-slate-200">Station {formatValue(data?.station_location_id)}, Chennai context</p>
                          </div>
                          <div>
                            <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Tool result</p>
                            <p className="text-sm text-slate-700 dark:text-slate-200">{step.result}</p>
                          </div>
                          <div>
                            <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Evidence used</p>
                            <List items={step.evidence} />
                          </div>
                          <div>
                            <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Limitations</p>
                            <List items={step.limitations} />
                          </div>
                        </div>
                      </details>
                    ))}
                  </div>
                </Card>
              ) : null}

              {screen === "advisory" ? (
                <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
                  <Card className="p-5">
                    <SectionTitle label="Citizen advisory" title="Approval-required public message" />
                    <div className="flex flex-wrap gap-2">
                      <Pill tone="teal">English</Pill>
                      <Pill>Hindi</Pill>
                      <Pill tone="slate">Tamil planned</Pill>
                    </div>
                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="mb-2 text-sm font-semibold text-slate-950 dark:text-slate-100">English advisory</p>
                        <textarea readOnly value={advisory?.english_advisory ?? ""} className="h-44 w-full rounded-xl border border-slate-300 p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/70 dark:text-slate-100" />
                      </div>
                      <div>
                        <p className="mb-2 text-sm font-semibold text-slate-950 dark:text-slate-100">Hindi advisory</p>
                        <textarea readOnly value={advisory?.hindi_advisory ?? ""} className="h-44 w-full rounded-xl border border-slate-300 p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950/70 dark:text-slate-100" />
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={() => void runCommand("regenerate-advisory", "Regenerate citizen advisory", "Operator requested advisory regeneration.")}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold dark:border-slate-700 dark:text-slate-100 dark:hover:bg-slate-800"
                      >
                        {commandPending === "regenerate-advisory:Regenerate citizen advisory" ? "Regenerating..." : "Regenerate"}
                      </button>
                      <button
                        onClick={() => {
                          void navigator.clipboard?.writeText(advisory?.english_advisory ?? "");
                          setCommandStatus("English advisory copied locally. Publishing still requires backend approval.");
                        }}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold dark:border-slate-700 dark:text-slate-100 dark:hover:bg-slate-800"
                      >
                        Copy
                      </button>
                      <button
                        onClick={() => void runCommand("approve-advisory", "Approve citizen advisory for publishing", "Human operator approved advisory text for publishing workflow.")}
                        className="rounded-lg bg-teal-700 px-3 py-2 text-sm font-semibold text-white"
                      >
                        {commandPending === "approve-advisory:Approve citizen advisory for publishing" ? "Approving..." : "Approve for Publishing"}
                      </button>
                    </div>
                  </Card>
                  <Card className="p-5">
                    <div className="mx-auto max-w-[300px] rounded-[2rem] border-8 border-slate-900 bg-slate-950 p-3 shadow-xl">
                      <div className="rounded-[1.4rem] bg-white p-4 dark:bg-slate-100">
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">AirGuard Advisory</p>
                        <p className="mt-3 text-sm text-slate-500">Area: Station {formatValue(data?.station_location_id)} surroundings</p>
                        <p className="text-sm text-slate-500">Level: {titleize(advisory?.advisory_level)}</p>
                        <p className="mt-4 text-sm leading-6 text-slate-800">{advisory?.english_advisory ?? FALLBACK}</p>
                        <p className="mt-4 font-semibold text-slate-950">Sensitive groups</p>
                        <List items={advisory?.who_should_take_care} />
                      </div>
                    </div>
                  </Card>
                </div>
              ) : null}

              {screen === "reports" ? (
                <Card className="mx-auto max-w-4xl p-8">
                  <div className="border-b border-slate-200 pb-5 dark:border-slate-700">
                    <p className="text-sm font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Official municipal decision memo</p>
                    <h2 className="mt-2 text-3xl font-semibold text-slate-950 dark:text-slate-50">AirGuard AI Response Memo</h2>
                    <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Date: {formatDateTime(data?.generated_at)} | Location: {data?.city ?? "Chennai"} | Station {formatValue(data?.station_location_id)}</p>
                  </div>
                  <div className="mt-6 grid gap-6 md:grid-cols-2">
                    <div>
                      <h3 className="font-semibold text-slate-950 dark:text-slate-50">Operational status</h3>
                      <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">{supervisor?.reasoning_summary ?? FALLBACK}</p>
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-950 dark:text-slate-50">AQI and forecast</h3>
                      <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">
                        AQI {formatValue(summary.cpcb_aqi ?? summary.current_estimated_aqi)} ({formatValue(summary.cpcb_aqi_category ?? summary.current_estimated_aqi_category)}). Forecast method: {formatValue(forecast?.best_overall)}.
                      </p>
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-950 dark:text-slate-50">Recommended interventions</h3>
                      <List items={actions.map((action) => action.action ?? FALLBACK)} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-950 dark:text-slate-50">Claims that must not be made</h3>
                      <List items={data?.claims_to_avoid} />
                    </div>
                  </div>
                  <div className="mt-8 rounded-xl border border-slate-300 p-5 dark:border-slate-700 dark:bg-slate-950/40">
                    <p className="font-semibold text-slate-950 dark:text-slate-50">Human approval/signature</p>
                    <div className="mt-8 border-t border-slate-300 pt-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">Ward engineer / command duty officer</div>
                  </div>
                  <button
                    onClick={() => void runCommand("export-memo", "Export decision memo", "Operator requested municipal memo export.")}
                    className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
                  >
                    {commandPending === "export-memo:Export decision memo" ? "Exporting..." : "Export PDF"}
                  </button>
                </Card>
              ) : null}

              {screen === "data" ? (
                <Card className="p-5">
                  <SectionTitle label="Data sources" title="Freshness and pipeline health" />
                  <div className="grid gap-3 md:grid-cols-3">
                    <StatCard label="Station mode" value={isRealPilot ? "REAL STATION PILOT" : "SYNTHETIC CITY DEMO"} detail={isRealPilot ? `Station ${formatValue(data?.station_location_id)}` : "Not live regulatory data"} tone={isRealPilot ? "teal" : "neutral"} />
                    <StatCard label="Source reading" value={formatDateTime(sourceTime)} detail={stale ? "STALE DATA" : "Fresh"} tone={stale ? "amber" : "teal"} />
                    <StatCard label="Satellite images" value={remote?.collection_image_count} detail={remote?.relative_no2_signal} />
                  </div>
                  <div className="mt-5">
                    <SectionTitle title="Guardrails" />
                    <div className="grid gap-5 md:grid-cols-3">
                      <div>
                        <h3 className="mb-2 font-semibold text-slate-950 dark:text-slate-50">Safe claims</h3>
                        <List items={data?.safe_claims} />
                      </div>
                      <div>
                        <h3 className="mb-2 font-semibold text-slate-950 dark:text-slate-50">Claims to avoid</h3>
                        <List items={data?.claims_to_avoid} />
                      </div>
                      <div>
                        <h3 className="mb-2 font-semibold text-slate-950 dark:text-slate-50">Limitations</h3>
                        <List items={data?.limitations} />
                      </div>
                    </div>
                  </div>
                </Card>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
