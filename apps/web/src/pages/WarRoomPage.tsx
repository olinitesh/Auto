import { useEffect, useMemo, useRef, useState } from "react";

import "./comparison.css";

type WarRoomEvent = {
  event_type: string;
  session_id?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
};

type NegotiationMessage = {
  id: string;
  direction: string;
  channel: string;
  sender_identity: string;
  body: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

type PlaybookPolicy = {
  playbook?: string;
  tone?: string;
  effective_target_otd?: number | null;
  max_rounds?: number;
  concession_step?: number;
};

type NegotiationSessionDetail = {
  id: string;
  status: string;
  playbook?: string;
  playbook_policy?: PlaybookPolicy | null;
  best_offer_otd?: number;
  autopilot_enabled?: boolean;
  autopilot_mode?: string;
  messages: NegotiationMessage[];
};

type EnqueueRoundResponse = {
  session_id: string;
  job_id: string;
  queue: string;
  status: string;
};

type WarRoomPageProps = {
  sessionId: string;
  returnTo?: string;
};

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "/api";

function formatEventTime(value?: string): string {
  if (!value) {
    return "live";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function eventTitle(event: WarRoomEvent): string {
  const eventType = (event.event_type || "").trim();
  if (eventType === "negotiation.playbook.updated") {
    return "Playbook Changed";
  }
  if (eventType === "negotiation.round.queued") {
    return "Round Queued";
  }
  if (eventType === "negotiation.status.updated") {
    return "Status Updated";
  }
  if (eventType === "negotiation.message.sent") {
    return "Outbound AI Message";
  }
  if (eventType === "negotiation.message.received") {
    return "Inbound Dealer Message";
  }
  return eventType || "warroom.event";
}

function readPolicy(value: unknown): PlaybookPolicy | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as PlaybookPolicy;
}

function eventIsInbound(eventType: string, payload: Record<string, unknown>): boolean {
  const direction = String(payload.direction || "").toLowerCase();
  return eventType === "negotiation.message.received" || eventType === "history.inbound" || direction === "inbound";
}

function eventIsOutbound(eventType: string, payload: Record<string, unknown>): boolean {
  const direction = String(payload.direction || "").toLowerCase();
  return eventType === "negotiation.message.sent" || eventType === "history.outbound" || direction === "outbound";
}

export function WarRoomPage({ sessionId, returnTo }: WarRoomPageProps) {
  const [events, setEvents] = useState<WarRoomEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<NegotiationSessionDetail | null>(null);
  const [queueingRound, setQueueingRound] = useState(false);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const wsUrl = useMemo(() => {
    const base = (import.meta.env.VITE_WS_BASE_URL as string | undefined)?.replace(/\/$/, "");
    if (base) {
      return `${base}/ws/negotiations/${sessionId}`;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname;
    const localHosts = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);
    if (localHosts.has(host)) {
      return protocol + "//" + host + ":8020/ws/negotiations/" + sessionId;
    }
    return protocol + "//" + window.location.host + "/ws/negotiations/" + sessionId;
  }, [sessionId]);

  const inboundCount = useMemo(
    () => events.filter((event) => event.event_type.toLowerCase().includes("inbound")).length,
    [events],
  );

  const outboundCount = useMemo(
    () => events.filter((event) => event.event_type.toLowerCase().includes("outbound")).length,
    [events],
  );

  const effectiveTarget = useMemo(() => {
    const value = sessionDetail?.playbook_policy?.effective_target_otd;
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }, [sessionDetail]);

  useEffect(() => {
    void loadHistory();
    return () => {
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [sessionId]);

  async function loadHistory() {
    setLoadingHistory(true);
    setHistoryError(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/${sessionId}`);
      if (!response.ok) {
        throw new Error(`History load failed (${response.status})`);
      }

      const session = (await response.json()) as NegotiationSessionDetail;
      setSessionDetail(session);
      setSessionStatus(session.status ?? null);

      const backfillEvents: WarRoomEvent[] = (session.messages ?? [])
        .slice()
        .reverse()
        .map((message) => ({
          event_type: `history.${message.direction}`,
          session_id: session.id,
          timestamp: message.created_at,
          payload: {
            message_id: message.id,
            direction: message.direction,
            channel: message.channel,
            sender_identity: message.sender_identity,
            body: message.body,
            metadata: message.metadata ?? {},
          },
        }));

      setEvents((prev) => {
        if (prev.length === 0) {
          return backfillEvents.slice(0, 100);
        }
        return [...prev, ...backfillEvents].slice(0, 100);
      });
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setLoadingHistory(false);
    }
  }

  async function queueRound(): Promise<void> {
    setQueueingRound(true);
    setQueueError(null);
    setQueueStatus(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/${sessionId}/autonomous-round`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: "Buyer" }),
      });
      if (!response.ok) {
        throw new Error(`Queue round failed (${response.status})`);
      }

      const data = (await response.json()) as EnqueueRoundResponse;
      setQueueStatus(`Round queued: ${data.job_id}`);
      setEvents((prev) => [
        {
          event_type: "negotiation.round.queued",
          session_id: sessionId,
          timestamp: new Date().toISOString(),
          payload: {
            job_id: data.job_id,
            queue: data.queue,
            source: "warroom-manual",
            playbook: sessionDetail?.playbook ?? "balanced",
            playbook_policy: sessionDetail?.playbook_policy ?? null,
          },
        },
        ...prev,
      ].slice(0, 100));
      await loadHistory();
    } catch (err) {
      setQueueError(err instanceof Error ? err.message : "Failed to queue round");
    } finally {
      setQueueingRound(false);
    }
  }

  async function updateSessionStatusAction(nextStatus: "active" | "closed"): Promise<void> {
    setActionLoading(nextStatus);
    setActionError(null);
    setActionStatus(null);

    try {
      const response = await fetch(`${apiBase}/negotiations/${sessionId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus, source: "warroom", actor: "operator" }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Status update failed (${response.status})`);
      }
      setActionStatus(`Session status updated: ${nextStatus}`);
      await loadHistory();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setActionLoading(null);
    }
  }

  async function pauseAutopilot(): Promise<void> {
    setActionLoading("autopilot");
    setActionError(null);
    setActionStatus(null);

    try {
      if (!sessionDetail?.autopilot_enabled) {
        setActionStatus("Autopilot is already paused.");
        return;
      }

      const response = await fetch(`${apiBase}/negotiations/${sessionId}/autopilot`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: false, mode: "manual" }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Autopilot update failed (${response.status})`);
      }
      setActionStatus("Autopilot paused.");
      await loadHistory();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to pause autopilot");
    } finally {
      setActionLoading(null);
    }
  }

  function connect() {
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    setFeedError(null);
    setConnecting(true);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setConnecting(false);
      setFeedError(null);
    };
    socket.onerror = () => {
      setConnected(false);
      setConnecting(false);
      setFeedError(
        "Live feed connection failed. Verify war-room realtime service is running and reachable at " + wsUrl + ".",
      );
    };
    socket.onclose = () => {
      setConnected(false);
      setConnecting(false);
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
    };
    socket.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data) as WarRoomEvent;
        setEvents((prev) => [parsed, ...prev].slice(0, 100));
      } catch {
        setEvents((prev) => [{ event_type: "warroom.raw", payload: { data: msg.data } }, ...prev].slice(0, 100));
      }
    };
  }

  return (
    <main className="comparison-page">
      <section className="hero warroom-hero">
        <p className="kicker">Negotiation Ops</p>
        <h1>Negotiation Command Center</h1>
        <p className="subtitle">Live events, history replay, and session telemetry for autonomous negotiation execution.</p>
        <div className="hero-meta">
          <span className={`pill ${connected ? "pill-live" : "pill-muted"}`}>{connected ? "Live Socket" : "Socket Offline"}</span>
          <span className="pill">Session {sessionId}</span>
          {sessionStatus && <span className="pill">Status {sessionStatus}</span>}
          <span className="pill">Events {events.length}</span>
          <span className="pill">Inbound {inboundCount}</span>
          <span className="pill">Outbound {outboundCount}</span>
          {sessionDetail?.playbook && <span className="pill">Playbook {sessionDetail.playbook}</span>}
        </div>
      </section>

      <section className="panel warroom-toolbar">
        <div className="actions warroom-actions">
          <a className="btn" href={returnTo || "/?workspace=offers"}>
            Back To Workspace
          </a>
          <button onClick={connect} className="btn primary" type="button">
            {connected ? "Connected" : connecting ? "Connecting..." : "Connect Feed"}
          </button>
          <button onClick={() => void loadHistory()} className="btn" type="button" disabled={loadingHistory}>
            {loadingHistory ? "Loading History..." : "Reload History"}
          </button>
        </div>
        <div className="warroom-preview-row">
          <span className="pill">Effective Target {effectiveTarget !== null ? `$${effectiveTarget.toLocaleString()}` : "n/a"}</span>
          {sessionDetail?.playbook_policy?.max_rounds !== undefined && (
            <span className="pill">Max Rounds {sessionDetail.playbook_policy.max_rounds}</span>
          )}
          {sessionDetail?.playbook_policy?.concession_step !== undefined && (
            <span className="pill">Concession ${Number(sessionDetail.playbook_policy.concession_step).toLocaleString()}</span>
          )}
          <button className="btn" type="button" onClick={() => void queueRound()} disabled={queueingRound}>
            {queueingRound ? "Queueing..." : "Queue Round"}
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => void updateSessionStatusAction("closed")}
            disabled={actionLoading === "closed" || sessionStatus === "closed"}
          >
            {actionLoading === "closed" ? "Closing..." : "Close Session"}
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => void updateSessionStatusAction("active")}
            disabled={actionLoading === "active" || sessionStatus !== "closed"}
          >
            {actionLoading === "active" ? "Reopening..." : "Reopen Session"}
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => void pauseAutopilot()}
            disabled={actionLoading === "autopilot"}
          >
            {actionLoading === "autopilot" ? "Pausing..." : "Pause Autopilot"}
          </button>
        </div>
        {queueStatus && <p className="success">{queueStatus}</p>}
        {queueError && <p className="error">{queueError}</p>}
        {actionStatus && <p className="success">{actionStatus}</p>}
        {actionError && <p className="error">{actionError}</p>}
        {feedError && <p className="error">{feedError}</p>}
      </section>

      {historyError && <p className="error">{historyError}</p>}

      <section className="panel">
        {events.length === 0 ? (
          <p className="empty">No events yet. Queue a round or wait for inbound dealer events.</p>
        ) : (
          <div className="warroom-feed">
            {events.map((event, index) => {
              const payload: Record<string, unknown> = event.payload ?? {};
              const nextPolicy = readPolicy(payload.playbook_policy);
              const prevPolicy = readPolicy(payload.previous_playbook_policy);
              const eventType = event.event_type || "";
              const inbound = eventIsInbound(eventType, payload);
              const outbound = eventIsOutbound(eventType, payload);
              const bodyText = typeof payload.body === "string" ? payload.body : JSON.stringify(payload, null, 2);
              const senderLabel =
                typeof payload.sender_identity === "string" && payload.sender_identity
                  ? payload.sender_identity
                  : typeof payload.sender === "string" && payload.sender
                    ? payload.sender
                    : inbound
                      ? "Dealer"
                      : outbound
                        ? "AI Assistant"
                        : eventTitle(event);

              return (
                <article className={`warroom-event-card ${inbound ? "chat-inbound" : outbound ? "chat-outbound" : "chat-system"}`} key={`${event.event_type}-${index}`}>
                  <div className="warroom-event-head">
                    <strong>{senderLabel}</strong>
                    <span>{formatEventTime(event.timestamp)}</span>
                  </div>
                  {(inbound || outbound) && <p className="warroom-chat-body">{bodyText}</p>}
                  {!(inbound || outbound) && event.event_type === "negotiation.playbook.updated" && (
                    <div className="warroom-event-inline">
                      <span className="pill">Before {(payload.previous_playbook as string) || "n/a"}</span>
                      <span className="pill">After {(payload.playbook as string) || "n/a"}</span>
                      {prevPolicy?.effective_target_otd !== undefined && prevPolicy?.effective_target_otd !== null && (
                        <span className="pill">Prev Target ${Number(prevPolicy.effective_target_otd).toLocaleString()}</span>
                      )}
                      {nextPolicy?.effective_target_otd !== undefined && nextPolicy?.effective_target_otd !== null && (
                        <span className="pill">New Target ${Number(nextPolicy.effective_target_otd).toLocaleString()}</span>
                      )}
                    </div>
                  )}
                  {!(inbound || outbound) && event.event_type === "negotiation.status.updated" && (
                    <div className="warroom-event-inline">
                      <span className="pill">From {(payload.previous_status as string) || "n/a"}</span>
                      <span className="pill">To {(payload.status as string) || "n/a"}</span>
                      <span className="pill">Source {(payload.source as string) || "api"}</span>
                      <span className="pill">Actor {(payload.actor as string) || "operator"}</span>
                    </div>
                  )}
                  {(inbound || outbound) && (
                    <div className="warroom-event-inline">
                      <span className="pill">{eventTitle(event)}</span>
                      {typeof payload.channel === "string" && <span className="pill">{String(payload.channel).toUpperCase()}</span>}
                    </div>
                  )}
                  {!(inbound || outbound) && <pre className="warroom-payload">{JSON.stringify(payload, null, 2)}</pre>}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

