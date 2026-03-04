import { useEffect, useMemo, useState } from "react";

import "./comparison.css";

type VehicleTarget = {
  make: string;
  model: string;
  year: number;
  trim?: string;
};

type DealerSiteInput = {
  dealer_id: string;
  dealer_name: string;
  dealer_zip: string;
  brand: string;
  site_url: string;
  inventory_url: string;
  adapter_key: string;
};

type DealerOffer = {
  offer_id: string;
  dealership_id: string;
  dealership_name: string;
  distance_miles: number;
  vehicle_id: string;
  vehicle_label: string;
  otd_price: number;
  fees: number;
  market_adjustment: number;
  specs_score: number;
  data_provider?: string;
  days_on_market?: number;
  days_on_market_source?: string;
  days_on_market_bucket?: string;
  price_drop_7d?: number;
  price_drop_30d?: number;
  inventory_status?: string;
  is_in_transit?: boolean;
  is_pre_sold?: boolean;
  is_hidden?: boolean;
  listing_url?: string;
  dealer_url?: string;
};

type RankedOffer = {
  rank: number;
  offer: DealerOffer;
  score: number;
  score_breakdown: Record<string, number>;
};

type OfferHistoryPoint = {
  otd_price: number;
  seen_at: string;
  data_provider?: string;
};

type OfferHistoryResponse = {
  dealership_id: string;
  vehicle_id: string;
  first_seen_at?: string;
  last_seen_at?: string;
  days_on_market?: number;
  points: OfferHistoryPoint[];
};

type OfferTrendKey = {
  dealership_id: string;
  vehicle_id: string;
};

type OfferTrendItem = {
  dealership_id: string;
  vehicle_id: string;
  first_seen_at?: string;
  last_seen_at?: string;
  days_on_market?: number;
  days_on_market_bucket?: string;
  price_drop_7d?: number;
  price_drop_30d?: number;
  snapshot_count: number;
};

type OfferTrendsBulkResponse = { trends: OfferTrendItem[] };
type OfferSearchResponse = { offers: DealerOffer[] };
type OfferRankResponse = { ranked_offers: RankedOffer[] };
type IngestFallbackResponse = {
  provider: string;
  jobs_collected: number;
  normalized_count: number;
  inserted: number;
  updated: number;
};

type SavedSearch = {
  id: string;
  name: string;
  user_zip: string;
  radius_miles: number;
  budget_otd: number;
  targets: VehicleTarget[];
  dealer_sites?: DealerSiteInput[];
  include_in_transit: boolean;
  include_pre_sold: boolean;
  include_hidden: boolean;
  created_at: string;
  updated_at: string;
};

type SavedSearchListResponse = { searches: SavedSearch[] };
type SavedSearchDeleteResponse = { deleted: boolean };
type SavedSearchAlert = {
  id: string;
  saved_search_id: string;
  alert_type: string;
  dealership_id: string;
  vehicle_id: string;
  title: string;
  message: string;
  metadata?: Record<string, unknown>;
  acknowledged: boolean;
  created_at: string;
  seen_at: string;
};

type SavedSearchAlertListResponse = {
  alerts: SavedSearchAlert[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};
type SavedSearchAlertAckResponse = { acknowledged: boolean };
type SavedSearchAlertAckAllResponse = { acknowledged_count: number };

type NegotiationDecision = {
  action: string;
  response_text: string;
  anchor_otd: number;
  rationale: string;
};

type StartNegotiationResponse = {
  session_id: string;
  status: string;
  decision: NegotiationDecision;
};

type EnqueueRoundResponse = {
  session_id: string;
  job_id: string;
  queue: string;
  status: string;
};

type JobStatusResponse = {
  job_id: string;
  status: string;
  queue?: string;
  enqueued_at?: string;
  started_at?: string;
  ended_at?: string;
  session_id?: string;
  error?: string;
};

type InboundDraft = {
  channel: "email" | "sms" | "voice";
  sender_identity: string;
  body: string;
};

type NegotiationSession = {
  id: string;
  user_id: string;
  saved_search_id?: string;
  offer_id?: string;
  dealership_id: string;
  dealership_name?: string;
  vehicle_id: string;
  vehicle_label?: string;
  status: string;
  best_offer_otd?: number;
  autopilot_enabled?: boolean;
  autopilot_mode?: string;
  last_job_id?: string;
  last_job_status?: string;
  last_job_at?: string;
  created_at: string;
  updated_at: string;
};

type AlertSeverity = {
  level: "high" | "medium" | "low";
  icon: string;
  label: string;
  className: string;
};

const apiBase = "http://localhost:8000";

const emptyDealerSite: DealerSiteInput = {
  dealer_id: "",
  dealer_name: "",
  dealer_zip: "",
  brand: "",
  site_url: "",
  inventory_url: "",
  adapter_key: "",
};

const MAKE_MODEL_OPTIONS: Record<string, string[]> = {
  Honda: ["Civic", "Accord", "CR-V", "CR-V Hybrid", "HR-V", "Pilot", "Odyssey"],
  Toyota: ["Corolla", "Camry", "RAV4", "RAV4 Hybrid", "Highlander", "Prius", "Tacoma"],
  Subaru: ["Crosstrek", "Forester", "Outback", "Ascent", "Impreza", "Legacy"],
  Mazda: ["CX-5", "CX-50", "CX-90", "Mazda3"],
  Hyundai: ["Elantra", "Sonata", "Tucson", "Santa Fe", "Palisade"],
  Kia: ["Forte", "K5", "Sportage", "Sorento", "Telluride"],
};

function normalizeModelAndTrim(selectedModel: string, selectedTrim: string): { model: string; trim?: string } {
  const modelValue = selectedModel.trim();
  const trimValue = selectedTrim.trim();

  if (/\bhybrid\b/i.test(modelValue)) {
    const modelWithoutHybrid = modelValue.replace(/\bhybrid\b/gi, "").replace(/\s+/g, " ").trim();
    if (modelWithoutHybrid) {
      return {
        model: modelWithoutHybrid,
        ...(trimValue ? { trim: trimValue } : { trim: "Hybrid" }),
      };
    }
  }

  return {
    model: modelValue,
    ...(trimValue ? { trim: trimValue } : {}),
  };
}

function getAlertSeverity(alertType: string): AlertSeverity {
  const normalized = alertType.trim().toLowerCase();

  if (normalized === "price_drop_30d") {
    return { level: "high", icon: "!!!", label: "High", className: "sev-high" };
  }
  if (normalized === "dom_threshold") {
    return { level: "medium", icon: "!!", label: "Medium", className: "sev-medium" };
  }
  if (normalized === "price_drop_7d") {
    return { level: "low", icon: "!", label: "Low", className: "sev-low" };
  }

  return { level: "medium", icon: "!", label: "Medium", className: "sev-medium" };
}

export function ComparisonPage() {
  const [userZip, setUserZip] = useState("18706");
  const [radiusMiles, setRadiusMiles] = useState(100);
  const [budgetOtd, setBudgetOtd] = useState(30000);
  const [make, setMake] = useState("Honda");
  const [model, setModel] = useState(MAKE_MODEL_OPTIONS.Honda[0]);
  const [year, setYear] = useState(2025);
  const [trim, setTrim] = useState("");

  const modelOptions = useMemo(() => MAKE_MODEL_OPTIONS[make] ?? [], [make]);

  useEffect(() => {
    if (modelOptions.length === 0) {
      setModel("");
      return;
    }
    if (!modelOptions.includes(model)) {
      setModel(modelOptions[0]);
    }
  }, [make, model, modelOptions]);

  useEffect(() => {
    void fetchSavedSearches();
    void fetchNegotiations();
  }, []);

  const [dealerSites, setDealerSites] = useState<DealerSiteInput[]>([]);
  const [includeInTransit, setIncludeInTransit] = useState(true);
  const [includePreSold, setIncludePreSold] = useState(false);
  const [includeHidden, setIncludeHidden] = useState(false);

  const [offers, setOffers] = useState<DealerOffer[]>([]);
  const [rankedOffers, setRankedOffers] = useState<RankedOffer[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingRank, setLoadingRank] = useState(false);
  const [loadingIngest, setLoadingIngest] = useState(false);
  const [historyByKey, setHistoryByKey] = useState<Record<string, OfferHistoryResponse>>({});
  const [historyLoadingByKey, setHistoryLoadingByKey] = useState<Record<string, boolean>>({});
  const [historyErrorByKey, setHistoryErrorByKey] = useState<Record<string, string | null>>({});
  const [expandedHistoryKeys, setExpandedHistoryKeys] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [savedSearchName, setSavedSearchName] = useState("");
  const [loadingSavedSearches, setLoadingSavedSearches] = useState(false);
  const [alerts, setAlerts] = useState<SavedSearchAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [acknowledgingAlerts, setAcknowledgingAlerts] = useState(false);
  const [alertTypeFilter, setAlertTypeFilter] = useState("all");
  const [includeAcknowledgedAlerts, setIncludeAcknowledgedAlerts] = useState(false);
  const [alertsPage, setAlertsPage] = useState(1);
  const [alertsPageSize, setAlertsPageSize] = useState(10);
  const [alertsTotal, setAlertsTotal] = useState(0);
  const [alertsTotalPages, setAlertsTotalPages] = useState(1);
  const [alertsCollapsed, setAlertsCollapsed] = useState(false);
  const [savedSearchesCollapsed, setSavedSearchesCollapsed] = useState(false);
  const [userName, setUserName] = useState("Buyer");
  const [userId, setUserId] = useState("local-user");
  const [selectedSavedSearchId, setSelectedSavedSearchId] = useState<string | null>(null);
  const [negotiations, setNegotiations] = useState<NegotiationSession[]>([]);
  const [loadingNegotiations, setLoadingNegotiations] = useState(false);
  const [startingNegotiationOfferId, setStartingNegotiationOfferId] = useState<string | null>(null);
  const [queueingSessionId, setQueueingSessionId] = useState<string | null>(null);
  const [settingAutopilotSessionId, setSettingAutopilotSessionId] = useState<string | null>(null);
  const [jobBySessionId, setJobBySessionId] = useState<Record<string, string>>({});
  const [jobStatusById, setJobStatusById] = useState<Record<string, JobStatusResponse>>({});
  const [inboundDraftBySessionId, setInboundDraftBySessionId] = useState<Record<string, InboundDraft>>({});
  const [sendingInboundSessionId, setSendingInboundSessionId] = useState<string | null>(null);
  const [negotiationStatusFilter, setNegotiationStatusFilter] = useState("all");
  const [negotiationStatus, setNegotiationStatus] = useState<string | null>(null);

  const targetPreview = useMemo(() => {
    const t = trim.trim();
    return `${year} ${make} ${model}${t ? ` ${t}` : ""}`;
  }, [year, make, model, trim]);

  const alertTypeOptions = useMemo(() => {
    return Array.from(new Set(alerts.map((alert) => alert.alert_type))).sort();
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    if (alertTypeFilter === "all") {
      return alerts;
    }
    return alerts.filter((alert) => alert.alert_type === alertTypeFilter);
  }, [alerts, alertTypeFilter]);

  const pagedAlerts = useMemo(() => {
    return filteredAlerts;
  }, [filteredAlerts]);

  const sessionByOfferId = useMemo(() => {
    const map = new Map<string, NegotiationSession>();
    for (const session of negotiations) {
      if (!session.offer_id) {
        continue;
      }
      if (!map.has(session.offer_id)) {
        map.set(session.offer_id, session);
      }
    }
    return map;
  }, [negotiations]);

  const negotiationStatuses = useMemo(() => {
    return Array.from(new Set(negotiations.map((s) => (s.status || "unknown").toLowerCase()))).sort();
  }, [negotiations]);

  const filteredNegotiations = useMemo(() => {
    if (negotiationStatusFilter === "all") {
      return negotiations;
    }
    return negotiations.filter((s) => (s.status || "").toLowerCase() === negotiationStatusFilter);
  }, [negotiations, negotiationStatusFilter]);

  useEffect(() => {
    void fetchAlerts();
  }, [includeAcknowledgedAlerts, alertsPage, alertsPageSize]);

  useEffect(() => {
    setAlertsPage(1);
  }, [alertsPageSize, includeAcknowledgedAlerts]);

  useEffect(() => {
    if (alertsPage > alertsTotalPages) {
      setAlertsPage(alertsTotalPages);
    }
  }, [alertsPage, alertsTotalPages]);

  function offerKey(offer: DealerOffer): string {
    return `${offer.dealership_id}::${offer.vehicle_id}`;
  }

  function formatSeenAt(value?: string): string {
    if (!value) {
      return "n/a";
    }
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) {
      return value;
    }
    return dt.toLocaleString();
  }

  function normalizeExternalUrl(value?: string): string | null {
    const raw = (value ?? "").trim();
    if (!raw) {
      return null;
    }

    if (/^https?:\/\//i.test(raw)) {
      return raw;
    }

    if (/^\/\//.test(raw)) {
      return `https:${raw}`;
    }

    // If provider returns host/path without scheme, treat as https.
    return `https://${raw}`;
  }

  async function buildApiErrorMessage(response: Response, fallbackLabel: string): Promise<string> {
    let bodyText = "";
    let detail = "";

    try {
      bodyText = await response.text();
      if (bodyText) {
        try {
          const parsed = JSON.parse(bodyText) as { detail?: unknown; message?: unknown };
          const rawDetail = parsed?.detail;
          if (typeof rawDetail === "string") {
            detail = rawDetail;
          } else if (Array.isArray(rawDetail) && rawDetail.length > 0) {
            const first = rawDetail[0] as { msg?: unknown };
            if (typeof first?.msg === "string") {
              detail = first.msg;
            }
          }
          if (!detail && typeof parsed?.message === "string") {
            detail = parsed.message;
          }
        } catch {
          detail = bodyText;
        }
      }
    } catch {
      detail = "";
    }

    const combined = `${response.status} ${detail || bodyText}`.toLowerCase();
    if (response.status === 429 || combined.includes("rate") || combined.includes("too many requests")) {
      return "Provider is rate-limited (429). Wait 30-90 seconds, then retry.";
    }

    return detail ? `${fallbackLabel} (${response.status}): ${detail}` : `${fallbackLabel} (${response.status})`;
  }

  function buildTargets(): VehicleTarget[] {
    const normalized = normalizeModelAndTrim(model, trim);
    return [
      {
        make: make.trim(),
        model: normalized.model,
        year,
        ...(normalized.trim ? { trim: normalized.trim } : {}),
      },
    ];
  }

  function buildDealerSites(): DealerSiteInput[] | undefined {
    const filtered = dealerSites
      .map((site) => ({
        dealer_id: site.dealer_id.trim(),
        dealer_name: site.dealer_name.trim(),
        dealer_zip: site.dealer_zip.trim(),
        brand: site.brand.trim(),
        site_url: site.site_url.trim(),
        inventory_url: site.inventory_url.trim(),
        adapter_key: site.adapter_key.trim().toLowerCase(),
      }))
      .filter(
        (site) =>
          site.dealer_id &&
          site.dealer_name &&
          site.dealer_zip &&
          site.brand &&
          site.site_url &&
          site.inventory_url &&
          site.adapter_key,
      );

    return filtered.length > 0 ? filtered : undefined;
  }

  async function fetchSavedSearches() {
    setLoadingSavedSearches(true);
    try {
      const response = await fetch(`${apiBase}/saved-searches`);
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Load saved searches failed"));
      }
      const data = (await response.json()) as SavedSearchListResponse;
      setSavedSearches(data.searches ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load saved searches");
    } finally {
      setLoadingSavedSearches(false);
    }
  }

  async function fetchNegotiations() {
    setLoadingNegotiations(true);
    try {
      const response = await fetch(`${apiBase}/negotiations`);
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Load negotiations failed"));
      }
      const data = (await response.json()) as NegotiationSession[];
      setNegotiations(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load negotiations");
    } finally {
      setLoadingNegotiations(false);
    }
  }

  async function startNegotiation(item: RankedOffer) {
    const offer = item.offer;
    const competitorBest = rankedOffers
      .map((entry) => entry.offer.otd_price)
      .filter((price) => Number.isFinite(price) && price > 0)
      .reduce((best, price) => Math.min(best, price), Number.POSITIVE_INFINITY);

    const hasCompetitorBest = Number.isFinite(competitorBest) && competitorBest > 0;

    let target = Math.min(budgetOtd, hasCompetitorBest ? competitorBest : budgetOtd, offer.otd_price);
    if ((offer.days_on_market ?? 0) >= 45) {
      target -= 200;
    }
    if ((offer.price_drop_30d ?? 0) >= 1000) {
      target -= 150;
    }
    target = Math.max(1000, Math.round(target));

    setStartingNegotiationOfferId(offer.offer_id);
    setNegotiationStatus(null);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId.trim() || "local-user",
          user_name: userName.trim() || "Buyer",
          saved_search_id: selectedSavedSearchId,
          offer_id: offer.offer_id,
          dealership_id: offer.dealership_id,
          dealership_name: offer.dealership_name,
          vehicle_id: offer.vehicle_id,
          vehicle_label: offer.vehicle_label,
          offer_rank: item.rank,
          days_on_market: offer.days_on_market,
          price_drop_7d: offer.price_drop_7d,
          price_drop_30d: offer.price_drop_30d,
          target_otd: target,
          dealer_otd: offer.otd_price,
          competitor_best_otd: hasCompetitorBest ? competitorBest : null,
        }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Start negotiation failed"));
      }

      const data = (await response.json()) as StartNegotiationResponse;
      setNegotiationStatus(`Session started: ${data.session_id}`);
      await fetchNegotiations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start negotiation");
    } finally {
      setStartingNegotiationOfferId(null);
    }
  }

  async function queueAutonomousRound(sessionId: string) {
    setQueueingSessionId(sessionId);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/${sessionId}/autonomous-round`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userName.trim() || "Buyer" }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Queue round failed"));
      }

      const data = (await response.json()) as EnqueueRoundResponse;
      setJobBySessionId((prev) => ({ ...prev, [sessionId]: data.job_id }));
      setJobStatusById((prev) => ({
        ...prev,
        [data.job_id]: { job_id: data.job_id, status: data.status, queue: data.queue, session_id: sessionId },
      }));
      setNegotiationStatus(`Round queued: job ${data.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to queue round");
    } finally {
      setQueueingSessionId(null);
    }
  }

  async function setSessionAutopilot(session: NegotiationSession, enabled: boolean) {
    setSettingAutopilotSessionId(session.id);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/${session.id}/autopilot`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, mode: enabled ? "autopilot" : "manual" }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Autopilot update failed"));
      }

      setNegotiationStatus(enabled ? "AI autopilot enabled." : "AI autopilot disabled.");
      await fetchNegotiations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update autopilot");
    } finally {
      setSettingAutopilotSessionId(null);
    }
  }
  async function fetchJobStatus(jobId: string) {
    try {
      const response = await fetch(`${apiBase}/jobs/${jobId}`);
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as JobStatusResponse;
      setJobStatusById((prev) => ({ ...prev, [jobId]: data }));
      if (["finished", "failed", "stopped", "canceled"].includes((data.status || "").toLowerCase())) {
        void fetchNegotiations();
      }
    } catch {
      // Ignore transient polling failures.
    }
  }

  useEffect(() => {
    const activeJobIds = Object.values(jobBySessionId).filter((id) => {
      const status = jobStatusById[id]?.status;
      return !status || ["queued", "started", "scheduled", "deferred"].includes(status);
    });

    if (activeJobIds.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      for (const jobId of activeJobIds) {
        void fetchJobStatus(jobId);
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [jobBySessionId, jobStatusById]);

  function getInboundDraft(sessionId: string): InboundDraft {
    return (
      inboundDraftBySessionId[sessionId] ?? {
        channel: "email",
        sender_identity: "dealer@example.com",
        body: "",
      }
    );
  }

  function updateInboundDraft(sessionId: string, patch: Partial<InboundDraft>) {
    setInboundDraftBySessionId((prev) => {
      const base =
        prev[sessionId] ??
        ({
          channel: "email",
          sender_identity: "dealer@example.com",
          body: "",
        } as InboundDraft);
      return { ...prev, [sessionId]: { ...base, ...patch } };
    });
  }

  async function simulateInboundReply(sessionId: string) {
    const draft = getInboundDraft(sessionId);
    const body = draft.body.trim();
    if (!body) {
      setError("Reply body is required.");
      return;
    }

    setSendingInboundSessionId(sessionId);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/negotiations/${sessionId}/simulate-reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channel: draft.channel,
          sender_identity: draft.sender_identity.trim() || undefined,
          user_name: userName.trim() || "Buyer",
          body,
        }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Simulate reply failed"));
      }

      const inboundResult = (await response.json()) as { autopilot_triggered?: boolean; job_id?: string; skip_reason?: string };
      if (inboundResult.autopilot_triggered && inboundResult.job_id) {
        setNegotiationStatus(`Inbound dealer reply recorded. AI round queued: ${inboundResult.job_id}`);
      } else if (inboundResult.skip_reason === "job_in_progress") {
        setNegotiationStatus("Inbound dealer reply recorded. Autopilot skipped because a job is already running.");
      } else {
        setNegotiationStatus("Inbound dealer reply recorded.");
      }
      updateInboundDraft(sessionId, { body: "" });
      await fetchNegotiations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to simulate inbound reply");
    } finally {
      setSendingInboundSessionId(null);
    }
  }

  async function fetchAlerts() {
    setLoadingAlerts(true);
    try {
      const response = await fetch(
        `${apiBase}/alerts?include_acknowledged=${includeAcknowledgedAlerts}&page=${alertsPage}&page_size=${alertsPageSize}`,
      );
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Load alerts failed"));
      }
      const data = (await response.json()) as SavedSearchAlertListResponse;
      setAlerts(data.alerts ?? []);
      setAlertsTotal(Number(data.total ?? 0));
      setAlertsTotalPages(Number(data.total_pages ?? 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      setLoadingAlerts(false);
    }
  }

  async function acknowledgeAlert(alertId: string) {
    try {
      const response = await fetch(`${apiBase}/alerts/${alertId}/ack`, { method: "POST" });
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Acknowledge alert failed"));
      }
      const _data = (await response.json()) as SavedSearchAlertAckResponse;
      await fetchAlerts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge alert");
    }
  }

  async function acknowledgeShownAlerts() {
    const ids = filteredAlerts.filter((item) => !item.acknowledged).map((item) => item.id);
    if (ids.length === 0) {
      return;
    }

    setAcknowledgingAlerts(true);
    try {
      const response = await fetch(`${apiBase}/alerts/ack-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_ids: ids }),
      });
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Bulk acknowledge failed"));
      }
      const _data = (await response.json()) as SavedSearchAlertAckAllResponse;
      await fetchAlerts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge shown alerts");
    } finally {
      setAcknowledgingAlerts(false);
    }
  }

  async function saveCurrentSearch() {
    const name = savedSearchName.trim() || targetPreview;

    try {
      const response = await fetch(`${apiBase}/saved-searches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          user_zip: userZip.trim(),
          radius_miles: radiusMiles,
          budget_otd: budgetOtd,
          targets: buildTargets(),
          dealer_sites: buildDealerSites(),
          include_in_transit: includeInTransit,
          include_pre_sold: includePreSold,
          include_hidden: includeHidden,
        }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Save search failed"));
      }

      const saved = (await response.json()) as SavedSearch;
      setSelectedSavedSearchId(saved.id);
      setSavedSearchName("");
      await fetchSavedSearches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save search");
    }
  }

  function applySavedSearch(search: SavedSearch) {
    setSelectedSavedSearchId(search.id);
    const first = search.targets[0];
    if (first) {
      setMake(first.make || "Honda");
      setModel(first.model || "Civic");
      setYear(Number(first.year) || 2025);
      setTrim(first.trim ?? "");
    }

    setUserZip(search.user_zip || "");
    setRadiusMiles(Number(search.radius_miles) || 100);
    setBudgetOtd(Number(search.budget_otd) || 1);
    setDealerSites(search.dealer_sites ?? []);
    setIncludeInTransit(Boolean(search.include_in_transit));
    setIncludePreSold(Boolean(search.include_pre_sold));
    setIncludeHidden(Boolean(search.include_hidden));
  }

  async function deleteSavedSearchById(searchId: string) {
    try {
      const response = await fetch(`${apiBase}/saved-searches/${searchId}`, { method: "DELETE" });
      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Delete search failed"));
      }
      const _data = (await response.json()) as SavedSearchDeleteResponse;
      setSavedSearches((prev) => prev.filter((item) => item.id !== searchId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete saved search");
    }
  }

  function addDealerSite() {
    setDealerSites((prev) => [...prev, { ...emptyDealerSite }]);
  }

  function removeDealerSite(index: number) {
    setDealerSites((prev) => prev.filter((_, idx) => idx !== index));
  }

  function updateDealerSite(index: number, key: keyof DealerSiteInput, value: string) {
    setDealerSites((prev) => prev.map((item, idx) => (idx === index ? { ...item, [key]: value } : item)));
  }

  async function ingestFallback() {
    setLoadingIngest(true);
    setError(null);
    setIngestStatus(null);

    try {
      const response = await fetch(`${apiBase}/ingest/fallback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_zip: userZip.trim(),
          radius_miles: radiusMiles,
          budget_otd: budgetOtd,
          targets: buildTargets(),
          dealer_sites: buildDealerSites(),
        }),
      });

      if (!response.ok) {
        throw new Error(`Fallback ingest failed (${response.status})`);
      }

      const data = (await response.json()) as IngestFallbackResponse;
      setIngestStatus(
        `Ingested via ${data.provider}: jobs=${data.jobs_collected}, normalized=${data.normalized_count}, inserted=${data.inserted}, updated=${data.updated}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run fallback ingest agent");
    } finally {
      setLoadingIngest(false);
    }
  }

  async function rankOfferList(offersToRank: DealerOffer[]): Promise<RankedOffer[]> {
    const response = await fetch(`${apiBase}/offers/rank`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget_otd: budgetOtd, offers: offersToRank }),
    });

    if (!response.ok) {
      throw new Error(await buildApiErrorMessage(response, "Rank failed"));
    }

    const data = (await response.json()) as OfferRankResponse;
    return data.ranked_offers ?? [];
  }

  async function fetchTrendSignals(offersToEnrich: DealerOffer[]): Promise<DealerOffer[]> {
    if (offersToEnrich.length === 0) {
      return offersToEnrich;
    }

    const trendKeys: OfferTrendKey[] = offersToEnrich.map((offer) => ({
      dealership_id: offer.dealership_id,
      vehicle_id: offer.vehicle_id,
    }));

    const response = await fetch(`${apiBase}/offers/trends/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ offers: trendKeys }),
    });

    if (!response.ok) {
      return offersToEnrich;
    }

    const data = (await response.json()) as OfferTrendsBulkResponse;
    const trendByKey = new Map(
      (data.trends ?? []).map((item) => [`${item.dealership_id}::${item.vehicle_id}`, item]),
    );

    return offersToEnrich.map((offer) => {
      const trend = trendByKey.get(`${offer.dealership_id}::${offer.vehicle_id}`);
      if (!trend) {
        return offer;
      }
      return {
        ...offer,
        days_on_market: offer.days_on_market ?? trend.days_on_market,
        days_on_market_bucket: trend.days_on_market_bucket ?? offer.days_on_market_bucket,
        price_drop_7d: trend.price_drop_7d ?? offer.price_drop_7d,
        price_drop_30d: trend.price_drop_30d ?? offer.price_drop_30d,
      };
    });
  }

  async function loadOfferHistory(offer: DealerOffer): Promise<void> {
    const key = offerKey(offer);

    setHistoryLoadingByKey((prev) => ({ ...prev, [key]: true }));
    setHistoryErrorByKey((prev) => ({ ...prev, [key]: null }));

    try {
      const params = new URLSearchParams({
        dealership_id: offer.dealership_id,
        vehicle_id: offer.vehicle_id,
        limit: "180",
      });
      const response = await fetch(`${apiBase}/offers/history?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`History failed (${response.status})`);
      }

      const data = (await response.json()) as OfferHistoryResponse;
      setHistoryByKey((prev) => ({ ...prev, [key]: data }));
    } catch (err) {
      setHistoryErrorByKey((prev) => ({
        ...prev,
        [key]: err instanceof Error ? err.message : "Failed to load history",
      }));
    } finally {
      setHistoryLoadingByKey((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function toggleOfferHistory(offer: DealerOffer) {
    const key = offerKey(offer);
    const isExpanded = expandedHistoryKeys[key] === true;

    if (isExpanded) {
      setExpandedHistoryKeys((prev) => ({ ...prev, [key]: false }));
      return;
    }

    setExpandedHistoryKeys((prev) => ({ ...prev, [key]: true }));
    if (!historyByKey[key] && !historyLoadingByKey[key]) {
      await loadOfferHistory(offer);
    }
  }

  async function searchAndRankOffers() {
    setLoadingSearch(true);
    setLoadingRank(true);
    setError(null);
    setRankedOffers([]);
    setHistoryByKey({});
    setHistoryLoadingByKey({});
    setHistoryErrorByKey({});
    setExpandedHistoryKeys({});

    try {
      const response = await fetch(`${apiBase}/offers/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_zip: userZip.trim(),
          radius_miles: radiusMiles,
          budget_otd: budgetOtd,
          targets: buildTargets(),
          dealer_sites: buildDealerSites(),
          include_in_transit: includeInTransit,
          include_pre_sold: includePreSold,
          include_hidden: includeHidden,
        }),
      });

      if (!response.ok) {
        throw new Error(await buildApiErrorMessage(response, "Search failed"));
      }

      const data = (await response.json()) as OfferSearchResponse;
      const nextOffers = data.offers ?? [];

      if (nextOffers.length === 0) {
        setOffers([]);
        setRankedOffers([]);
        return;
      }

      const hasTrendSignals = nextOffers.some(
        (offer) =>
          offer.days_on_market !== undefined ||
          offer.days_on_market_bucket !== undefined ||
          offer.price_drop_7d !== undefined ||
          offer.price_drop_30d !== undefined,
      );

      const enrichedOffers = hasTrendSignals ? nextOffers : await fetchTrendSignals(nextOffers);
      setOffers(enrichedOffers);

      const ranked = await rankOfferList(enrichedOffers);
      setRankedOffers(ranked);
    } catch (err) {
      setOffers([]);
      setRankedOffers([]);
      setError(err instanceof Error ? err.message : "Failed to search and rank offers");
    } finally {
      setLoadingSearch(false);
      setLoadingRank(false);
    }
  }

  async function rerankCurrentOffers() {
    if (offers.length === 0) {
      setError("Search offers first, then re-rank them.");
      return;
    }

    setLoadingRank(true);
    setError(null);

    try {
      const ranked = await rankOfferList(offers);
      setRankedOffers(ranked);
    } catch (err) {
      setRankedOffers([]);
      setError(err instanceof Error ? err.message : "Failed to rank offers");
    } finally {
      setLoadingRank(false);
    }
  }

  function clampPercent(value: number, max: number): number {
    if (!Number.isFinite(value) || value <= 0 || max <= 0) {
      return 0;
    }
    return Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  }

  function buildOfferSignals(offer: DealerOffer): { value: number; domRisk: number; dropMomentum: number; feeLoad: number } {
    const dom = clampPercent(offer.days_on_market ?? 0, 90);
    const drop7d = clampPercent(offer.price_drop_7d ?? 0, 2000);
    const drop30d = clampPercent(offer.price_drop_30d ?? 0, 5000);
    const feeLoad = clampPercent(offer.fees + Math.max(offer.market_adjustment, 0), 5000);
    const dropMomentum = Math.max(drop7d, drop30d);

    return {
      domRisk: dom,
      dropMomentum,
      feeLoad,
      value: Math.max(0, Math.min(100, Math.round(100 - feeLoad * 0.4 - dom * 0.25 + dropMomentum * 0.35))),
    };
  }

  function renderTrendSparkline(offer: DealerOffer) {
    const history = historyByKey[offerKey(offer)];
    const points = (history?.points ?? []).slice(-8);

    if (points.length < 2) {
      return null;
    }

    const prices = points.map((point) => point.otd_price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const spread = Math.max(max - min, 1);

    const coords = prices
      .map((price, index) => {
        const x = (index / (prices.length - 1)) * 100;
        const y = ((max - price) / spread) * 100;
        return x + "," + y;
      })
      .join(" ");

    return (
      <div className="trend-sparkline" aria-label="price trend sparkline">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img">
          <polyline points={coords} />
        </svg>
      </div>
    );
  }

  function renderHistoryPanel(offer: DealerOffer) {
    const key = offerKey(offer);
    const expanded = expandedHistoryKeys[key] === true;
    const loading = historyLoadingByKey[key] === true;
    const response = historyByKey[key];
    const fetchError = historyErrorByKey[key];

    return (
      <div className="history-wrap">
        <button className="btn" type="button" onClick={() => void toggleOfferHistory(offer)}>
          {expanded ? "Hide Price History" : "View Price History"}
        </button>

        {expanded && (
          <div className="history-panel">
            {loading && <p className="empty">Loading history...</p>}
            {!loading && fetchError && <p className="error">{fetchError}</p>}
            {!loading && !fetchError && response && (
              <>
                <div className="stats history-meta">
                  <span>First Seen: {formatSeenAt(response.first_seen_at)}</span>
                  <span>Last Seen: {formatSeenAt(response.last_seen_at)}</span>
                  {response.days_on_market !== undefined && <span>Tracked DOM: {response.days_on_market}d</span>}
                </div>
                {response.points.length === 0 ? (
                  <p className="empty">No historical snapshots yet.</p>
                ) : (
                  <ul className="history-list">
                    {response.points.map((point, idx) => (
                      <li key={`${key}-${idx}`}>
                        <span>{formatSeenAt(point.seen_at)}</span>
                        <span>${point.otd_price.toLocaleString()}</span>
                        <span>{point.data_provider ?? "n/a"}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="comparison-page">
      <section className="hero">
        <p className="kicker">AutoHaggle</p>
        <h1>Find and rank dealer offers before negotiation</h1>
        <p className="subtitle">
          Search live listings, include incoming/hidden inventory if needed, and rank by price, specs, and fees.
        </p>
        <div className="hero-meta">
          <span className="pill">Active Alerts: {alerts.length}</span>
          <span className="pill">Saved Searches: {savedSearches.length}</span>
          <span className="pill">Negotiations: {negotiations.length}</span>
          <span className="pill">Active Search: {selectedSavedSearchId ?? "ad-hoc"}</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Vehicle Search</h2>
          <span className="pill">Target: {targetPreview}</span>
        </div>

        <div className="form-grid">
          <label>
            ZIP Code
            <input value={userZip} onChange={(e) => setUserZip(e.target.value)} placeholder="18706" />
          </label>
          <label>
            Radius (miles)
            <input
              type="number"
              min={1}
              max={250}
              value={radiusMiles}
              onChange={(e) => setRadiusMiles(Number(e.target.value) || 1)}
            />
          </label>
          <label>
            Budget OTD ($)
            <input
              type="number"
              min={1}
              value={budgetOtd}
              onChange={(e) => setBudgetOtd(Number(e.target.value) || 1)}
            />
          </label>
          <label>
            Make
            <select
              value={make}
              onChange={(e) => {
                setMake(e.target.value);
                setTrim("");
              }}
            >
              {Object.keys(MAKE_MODEL_OPTIONS).map((makeOption) => (
                <option key={makeOption} value={makeOption}>
                  {makeOption}
                </option>
              ))}
            </select>
          </label>
          <label>
            Model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {modelOptions.map((modelOption) => (
                <option key={modelOption} value={modelOption}>
                  {modelOption}
                </option>
              ))}
            </select>
          </label>
          <label>
            Year
            <input
              type="number"
              min={1990}
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || 2025)}
            />
          </label>
          <label>
            Buyer Name
            <input value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="Buyer" />
          </label>
          <label>
            Buyer ID
            <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="local-user" />
          </label>
          <label className="wide">
            Trim (optional)
            <input value={trim} onChange={(e) => setTrim(e.target.value)} placeholder="EX / Sport / XLE" />
          </label>
        </div>

        <div className="toggles">
          <label className="toggle">
            <input type="checkbox" checked={includeInTransit} onChange={(e) => setIncludeInTransit(e.target.checked)} />
            Include In-Transit
          </label>
          <label className="toggle">
            <input type="checkbox" checked={includePreSold} onChange={(e) => setIncludePreSold(e.target.checked)} />
            Include Pre-Sold
          </label>
          <label className="toggle">
            <input type="checkbox" checked={includeHidden} onChange={(e) => setIncludeHidden(e.target.checked)} />
            Include Hidden Inventory
          </label>
        </div>

        <div className="actions">
          <button className="btn primary" onClick={searchAndRankOffers} disabled={loadingSearch || loadingRank}>
            {loadingSearch || loadingRank ? "Searching + Ranking..." : "Search + Rank Offers"}
          </button>
          <button className="btn" onClick={rerankCurrentOffers} disabled={loadingRank || offers.length === 0}>
            {loadingRank ? "Ranking..." : "Re-rank Current"}
          </button>
          <button className="btn" onClick={ingestFallback} disabled={loadingIngest}>
            {loadingIngest ? "Ingesting..." : "Run Parser Agent"}
          </button>
          {negotiations[0] ? (
            <a className="btn link" href={`/?view=warroom&sessionId=${negotiations[0].id}`}>
              Open Latest War Room
            </a>
          ) : (
            <button className="btn" type="button" disabled>
              Open Latest War Room
            </button>
          )}
        </div>
        <div className="panel stacked-panel">
          <div className="panel-header">
            <h2>Active Alerts</h2>
            <button className="btn section-toggle" type="button" onClick={() => setAlertsCollapsed((v) => !v)}>
              {alertsCollapsed ? "Expand" : "Collapse"}
            </button>
            <div className="panel-head-actions">
              <span className="pill">{pagedAlerts.length} page / {filteredAlerts.length} filtered / {alertsTotal} total</span>
              <button
                className="btn"
                type="button"
                onClick={() => void acknowledgeShownAlerts()}
                disabled={acknowledgingAlerts || pagedAlerts.filter((item) => !item.acknowledged).length === 0}
              >
                {acknowledgingAlerts ? "Acknowledging..." : "Acknowledge Shown"}
              </button>
              <button className="btn" type="button" onClick={() => void fetchAlerts()} disabled={loadingAlerts}>
                {loadingAlerts ? "Refreshing..." : "Refresh"}
              </button>
            </div>
          </div>

          {!alertsCollapsed && (
            <>
              <div className="alert-filter-row">
                <label>
                  Alert Type
                  <select value={alertTypeFilter} onChange={(e) => setAlertTypeFilter(e.target.value)}>
                    <option value="all">All</option>
                    {alertTypeOptions.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="alert-filter-row">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={includeAcknowledgedAlerts}
                    onChange={(e) => setIncludeAcknowledgedAlerts(e.target.checked)}
                  />
                  Show Acknowledged
                </label>
                <label>
                  Page Size
                  <select value={alertsPageSize} onChange={(e) => setAlertsPageSize(Number(e.target.value) || 10)}>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </label>
              </div>

              {alerts.length === 0 ? (
                <p className="empty">No active alerts.</p>
              ) : filteredAlerts.length === 0 ? (
                <p className="empty">No alerts match this filter.</p>
              ) : (
                <div className="offer-list">
                  {pagedAlerts.map((alert) => {
                    const meta = alert.metadata ?? {};
                    const dom = typeof meta.days_on_market === "number" ? meta.days_on_market : undefined;
                    const drop7d = typeof meta.price_drop_7d === "number" ? meta.price_drop_7d : undefined;
                    const drop30d = typeof meta.price_drop_30d === "number" ? meta.price_drop_30d : undefined;
                    const severity = getAlertSeverity(alert.alert_type);

                    return (
                      <div className="offer-card" key={alert.id}>
                        <div className="offer-head">
                          <strong>{alert.title}</strong>
                          <span className={`alert-severity ${severity.className}`}>
                            <span aria-hidden="true">{severity.icon}</span>
                            <span>{severity.label}</span>
                          </span>
                        </div>
                        <p>{alert.message}</p>
                        <div className="stats">
                          <span>Dealer {alert.dealership_id}</span>
                          <span>Vehicle {alert.vehicle_id}</span>
                          {dom !== undefined && <span>DOM {dom}d</span>}
                          {drop7d !== undefined && <span>Drop 7d ${drop7d.toLocaleString()}</span>}
                          {drop30d !== undefined && <span>Drop 30d ${drop30d.toLocaleString()}</span>}
                          <span>Type {alert.alert_type}</span>
                          <span>{formatSeenAt(alert.created_at)}</span>
                        </div>
                        <div className="actions actions-tight">
                          <button className="btn" type="button" onClick={() => void acknowledgeAlert(alert.id)}>
                            Acknowledge
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {alertsTotal > 0 && (
                <div className="actions actions-spread">
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setAlertsPage((p) => Math.max(1, p - 1))}
                    disabled={alertsPage <= 1}
                  >
                    Prev
                  </button>
                  <span className="pill">Page {alertsPage} / {alertsTotalPages}</span>
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setAlertsPage((p) => Math.min(alertsTotalPages, p + 1))}
                    disabled={alertsPage >= alertsTotalPages}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="panel stacked-panel">
          <div className="panel-header">
            <h2>Saved Searches</h2>
            <button className="btn section-toggle" type="button" onClick={() => setSavedSearchesCollapsed((v) => !v)}>
              {savedSearchesCollapsed ? "Expand" : "Collapse"}
            </button>
            <button className="btn" type="button" onClick={() => void fetchSavedSearches()} disabled={loadingSavedSearches}>
              {loadingSavedSearches ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {!savedSearchesCollapsed && (
            <>
              <div className="actions actions-reset">
                <input
                  value={savedSearchName}
                  onChange={(e) => setSavedSearchName(e.target.value)}
                  placeholder="Name this search (optional)"
                  className="saved-search-name"
                />
                <button className="btn" type="button" onClick={() => void saveCurrentSearch()}>
                  Save Current Search
                </button>
              </div>

              {savedSearches.length === 0 ? (
                <p className="empty">No saved searches yet.</p>
              ) : (
                <div className="offer-list list-offset">
                  {savedSearches.map((search) => (
                    <div className="offer-card" key={search.id}>
                      <div className="offer-head">
                        <strong>{search.name}</strong>
                        <span>{search.user_zip}</span>
                      </div>
                      <div className="stats">
                        <span>Budget ${Number(search.budget_otd).toLocaleString()}</span>
                        <span>Radius {search.radius_miles} mi</span>
                        <span>
                          {search.targets
                            .map((target) => `${target.year} ${target.make} ${target.model}${target.trim ? ` ${target.trim}` : ""}`)
                            .join(" | ")}
                        </span>
                      </div>
                      <div className="actions actions-tight">
                        <button className="btn" type="button" onClick={() => applySavedSearch(search)}>
                          Load
                        </button>
                        <button className="btn" type="button" onClick={() => void deleteSavedSearchById(search.id)}>
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="panel stacked-panel">
          <div className="panel-header">
            <h2>Negotiation Sessions</h2>
            <div className="panel-head-actions">
              <span className="pill">{filteredNegotiations.length} shown / {negotiations.length} total</span>
              <button className="btn" type="button" onClick={() => void fetchNegotiations()} disabled={loadingNegotiations}>
                {loadingNegotiations ? "Refreshing..." : "Refresh"}
              </button>
            </div>
          </div>
          <div className="alert-filter-row">
            <label>
              Session Status
              <select value={negotiationStatusFilter} onChange={(e) => setNegotiationStatusFilter(e.target.value)}>
                <option value="all">All</option>
                {negotiationStatuses.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {negotiations.length === 0 ? (
            <p className="empty">No sessions yet. Start one from Ranked Shortlist.</p>
          ) : filteredNegotiations.length === 0 ? (
            <p className="empty">No sessions match this status.</p>
          ) : (
            <div className="offer-list list-offset">
              {filteredNegotiations.slice(0, 12).map((session) => {
                const sessionJobId = jobBySessionId[session.id];
                const sessionJobStatus = sessionJobId ? jobStatusById[sessionJobId] : undefined;

                return (
                <div className="offer-card" key={session.id}>
                  <div className="offer-head">
                    <strong>{session.dealership_name ?? session.dealership_id}</strong>
                    <span className="pill">{session.status}</span>
                  </div>
                  <div className="stats">
                    <span>{session.vehicle_label ?? session.vehicle_id}</span>
                    {session.best_offer_otd !== undefined && <span>Dealer OTD ${Number(session.best_offer_otd).toLocaleString()}</span>}
                    <span>{formatSeenAt(session.created_at)}</span>
                    {(sessionJobId || session.last_job_id) && <span>Job {(sessionJobId ?? session.last_job_id ?? "").slice(0, 8)}</span>}
                    {(sessionJobStatus?.status || session.last_job_status) && <span>Job Status {sessionJobStatus?.status ?? session.last_job_status}</span>}
                    {session.last_job_at && <span>Job At {formatSeenAt(session.last_job_at)}</span>}
                    <span>Autopilot {session.autopilot_enabled ? `ON (${session.autopilot_mode ?? "autopilot"})` : "OFF"}</span>
                  </div>
                  <div className="form-grid form-offset">
                    <label>
                      Inbound Channel
                      <select
                        value={getInboundDraft(session.id).channel}
                        onChange={(e) =>
                          updateInboundDraft(session.id, {
                            channel: (e.target.value as "email" | "sms" | "voice") || "email",
                          })
                        }
                      >
                        <option value="email">email</option>
                        <option value="sms">sms</option>
                        <option value="voice">voice</option>
                      </select>
                    </label>
                    <label>
                      Sender
                      <input
                        value={getInboundDraft(session.id).sender_identity}
                        onChange={(e) => updateInboundDraft(session.id, { sender_identity: e.target.value })}
                        placeholder="dealer@example.com / +1555..."
                      />
                    </label>
                    <label className="wide">
                      Dealer Reply
                      <input
                        value={getInboundDraft(session.id).body}
                        onChange={(e) => updateInboundDraft(session.id, { body: e.target.value })}
                        placeholder="We can do $31,250 OTD if financed today..."
                      />
                    </label>
                  </div>
                  <div className="link-actions">
                    <button
                      className="btn"
                      type="button"
                      onClick={() => void setSessionAutopilot(session, !session.autopilot_enabled)}
                      disabled={settingAutopilotSessionId === session.id}
                    >
                      {settingAutopilotSessionId === session.id
                        ? "Saving..."
                        : session.autopilot_enabled
                        ? "Disable AI Autopilot"
                        : "Enable AI Autopilot"}
                    </button>
                    <button
                      className="btn"
                      type="button"
                      onClick={() => void simulateInboundReply(session.id)}
                      disabled={sendingInboundSessionId === session.id}
                    >
                      {sendingInboundSessionId === session.id ? "Recording..." : "Simulate Dealer Reply"}
                    </button>
                    <button
                      className="btn"
                      type="button"
                      onClick={() => void queueAutonomousRound(session.id)}
                      disabled={queueingSessionId === session.id}
                    >
                      {queueingSessionId === session.id ? "Queueing..." : "Queue Round"}
                    </button>
                    <a className="btn link" href={`/?view=warroom&sessionId=${session.id}`}>
                      Open War Room
                    </a>
                  </div>
                </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="panel stacked-panel">
          <div className="panel-header">
            <h2>Dealer Sites (Optional)</h2>
            <button className="btn" onClick={addDealerSite} type="button">
              + Add Dealer Site
            </button>
          </div>
          {dealerSites.length === 0 ? (
            <p className="empty">No dealer sites configured. API/default sources will be used.</p>
          ) : (
            <div className="offer-list">
              {dealerSites.map((site, idx) => (
                <div className="offer-card" key={`dealer-site-${idx}`}>
                  <div className="form-grid">
                    <label>
                      Dealer ID
                      <input value={site.dealer_id} onChange={(e) => updateDealerSite(idx, "dealer_id", e.target.value)} />
                    </label>
                    <label>
                      Dealer Name
                      <input value={site.dealer_name} onChange={(e) => updateDealerSite(idx, "dealer_name", e.target.value)} />
                    </label>
                    <label>
                      Dealer ZIP
                      <input value={site.dealer_zip} onChange={(e) => updateDealerSite(idx, "dealer_zip", e.target.value)} />
                    </label>
                    <label>
                      Brand
                      <input value={site.brand} onChange={(e) => updateDealerSite(idx, "brand", e.target.value)} placeholder="Honda/Toyota" />
                    </label>
                    <label>
                      Adapter Key
                      <input value={site.adapter_key} onChange={(e) => updateDealerSite(idx, "adapter_key", e.target.value)} placeholder="honda/toyota" />
                    </label>
                    <label>
                      Site URL
                      <input value={site.site_url} onChange={(e) => updateDealerSite(idx, "site_url", e.target.value)} placeholder="https://dealer.example" />
                    </label>
                    <label className="wide">
                      Inventory URL
                      <input value={site.inventory_url} onChange={(e) => updateDealerSite(idx, "inventory_url", e.target.value)} placeholder="https://dealer.example/new-inventory" />
                    </label>
                  </div>
                  <div className="actions actions-tight">
                    <button className="btn" type="button" onClick={() => removeDealerSite(idx)}>
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {ingestStatus && <p className="success">{ingestStatus}</p>}
        {negotiationStatus && <p className="success">{negotiationStatus}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="results-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Search Results</h2>
            <span className="pill">{offers.length} offers</span>
          </div>

          {offers.length === 0 ? (
            <p className="empty">No offers yet. Run a search to populate your shortlist.</p>
          ) : (
            <div className="offer-list">
                            {offers.map((offer) => {
                const listingHref = normalizeExternalUrl(offer.listing_url);
                const dealerHref = normalizeExternalUrl(offer.dealer_url);
                const signals = buildOfferSignals(offer);

                return (
                  <div className="offer-card" key={offer.offer_id}>
                    <div className="offer-head">
                      <strong>{offer.vehicle_label}</strong>
                      <span>${offer.otd_price.toLocaleString()}</span>
                    </div>
                    <p>{offer.dealership_name}</p>
                    <div className="stats">
                      <span>{offer.distance_miles} mi</span>
                      <span>Fees ${offer.fees.toLocaleString()}</span>
                      <span>Adj. ${offer.market_adjustment.toLocaleString()}</span>
                      <span>Specs {offer.specs_score}/100</span>
                      {offer.days_on_market !== undefined && (
                        <span>
                          DOM {offer.days_on_market}d ({offer.days_on_market_source ?? "n/a"})
                        </span>
                      )}
                      {offer.days_on_market_bucket && <span>DOM Bucket {offer.days_on_market_bucket}</span>}
                      {offer.price_drop_7d !== undefined && offer.price_drop_7d > 0 && (
                        <span>Drop 7d ${offer.price_drop_7d.toLocaleString()}</span>
                      )}
                      {offer.price_drop_30d !== undefined && offer.price_drop_30d > 0 && (
                        <span>Drop 30d ${offer.price_drop_30d.toLocaleString()}</span>
                      )}
                      {offer.inventory_status && <span>Status {offer.inventory_status}</span>}
                      {offer.is_in_transit && <span className="tag">In-Transit</span>}
                      {offer.is_pre_sold && <span className="tag">Pre-Sold</span>}
                      {offer.is_hidden && <span className="tag">Hidden</span>}
                      {offer.data_provider && <span>Provider {offer.data_provider}</span>}
                    </div>
                    <div className="signal-grid">
                      <div className="signal-meter">
                        <span>Value</span>
                        <div className="meter-track"><div className="meter-fill" style={{ width: `${signals.value}%` }} /></div>
                      </div>
                      <div className="signal-meter">
                        <span>DOM Risk</span>
                        <div className="meter-track"><div className="meter-fill danger" style={{ width: `${signals.domRisk}%` }} /></div>
                      </div>
                      <div className="signal-meter">
                        <span>Drop Momentum</span>
                        <div className="meter-track"><div className="meter-fill accent" style={{ width: `${signals.dropMomentum}%` }} /></div>
                      </div>
                    </div>
                    {renderTrendSparkline(offer)}
                    <div className="link-actions">
                      {listingHref && (
                        <a className="btn link" href={listingHref} target="_blank" rel="noreferrer">
                          Open Listing
                        </a>
                      )}
                      {dealerHref && (
                        <a className="btn link" href={dealerHref} target="_blank" rel="noreferrer">
                          Dealer Site
                        </a>
                      )}
                    </div>
                    {renderHistoryPanel(offer)}
                  </div>
                );
              })}
            </div>
          )}
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Ranked Shortlist</h2>
            <span className="pill">{rankedOffers.length} ranked</span>
          </div>

          {rankedOffers.length === 0 ? (
            <p className="empty">Ranked results appear automatically after Search + Rank Offers.</p>
          ) : (
            <div className="offer-list">
                            {rankedOffers.map((item) => {
                const listingHref = normalizeExternalUrl(item.offer.listing_url);
                const dealerHref = normalizeExternalUrl(item.offer.dealer_url);
                const activeSession = sessionByOfferId.get(item.offer.offer_id);
                const signals = buildOfferSignals(item.offer);

                return (
                  <div className={`rank-card${item.rank === 1 ? " best" : ""}`} key={`${item.offer.offer_id}-${item.rank}`}>
                    <div className="rank-row">
                      <span className="rank">#{item.rank}</span>
                      <strong>{item.offer.dealership_name}</strong>
                      <span className="score">Score {item.score}</span>
                    </div>
                    {item.rank === 1 && <div className="best-pill">Best Deal</div>}
                    <p>{item.offer.vehicle_label}</p>
                    <div className="scorebar-wrap">
                      <div className="scorebar" style={{ width: `${Math.min(item.score, 100)}%` }} />
                    </div>
                    <div className="stats">
                      <span>OTD ${item.offer.otd_price.toLocaleString()}</span>
                      <span>Price {item.score_breakdown.price_score ?? 0}</span>
                      <span>Specs {item.score_breakdown.specs_score ?? 0}</span>
                      <span>Fees {item.score_breakdown.fee_score ?? 0}</span>
                      {item.offer.days_on_market !== undefined && <span>DOM {item.offer.days_on_market}d</span>}
                      {item.offer.days_on_market_bucket && <span>DOM Bucket {item.offer.days_on_market_bucket}</span>}
                      {item.offer.price_drop_7d !== undefined && item.offer.price_drop_7d > 0 && (
                        <span>Drop 7d ${item.offer.price_drop_7d.toLocaleString()}</span>
                      )}
                      {item.offer.price_drop_30d !== undefined && item.offer.price_drop_30d > 0 && (
                        <span>Drop 30d ${item.offer.price_drop_30d.toLocaleString()}</span>
                      )}
                      <span>Trend {item.score_breakdown.trend_score ?? 0}</span>
                    </div>
                    <div className="signal-grid">
                      <div className="signal-meter">
                        <span>Value</span>
                        <div className="meter-track"><div className="meter-fill" style={{ width: `${signals.value}%` }} /></div>
                      </div>
                      <div className="signal-meter">
                        <span>DOM Risk</span>
                        <div className="meter-track"><div className="meter-fill danger" style={{ width: `${signals.domRisk}%` }} /></div>
                      </div>
                      <div className="signal-meter">
                        <span>Drop Momentum</span>
                        <div className="meter-track"><div className="meter-fill accent" style={{ width: `${signals.dropMomentum}%` }} /></div>
                      </div>
                    </div>
                    {renderTrendSparkline(item.offer)}
                    <div className="link-actions">
                      <button
                        className="btn primary"
                        type="button"
                        onClick={() => void startNegotiation(item)}
                        disabled={startingNegotiationOfferId === item.offer.offer_id}
                      >
                        {startingNegotiationOfferId === item.offer.offer_id ? "Starting..." : "Start Negotiation"}
                      </button>
                      {activeSession && (
                        <>
                          <button
                            className="btn"
                            type="button"
                            onClick={() => void queueAutonomousRound(activeSession.id)}
                            disabled={queueingSessionId === activeSession.id}
                          >
                            {queueingSessionId === activeSession.id ? "Queueing..." : "Queue Round"}
                          </button>
                          {jobBySessionId[activeSession.id] && jobStatusById[jobBySessionId[activeSession.id]]?.status && (
                            <span className="pill">Job {jobStatusById[jobBySessionId[activeSession.id]]?.status}</span>
                          )}
                          <a className="btn link" href={`/?view=warroom&sessionId=${activeSession.id}`}>
                            Open Session
                          </a>
                        </>
                      )}
                      {listingHref && (
                        <a className="btn link" href={listingHref} target="_blank" rel="noreferrer">
                          Open Listing
                        </a>
                      )}
                      {dealerHref && (
                        <a className="btn link" href={dealerHref} target="_blank" rel="noreferrer">
                          Dealer Site
                        </a>
                      )}
                    </div>
                    {renderHistoryPanel(item.offer)}
                  </div>
                );
              })}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}


































