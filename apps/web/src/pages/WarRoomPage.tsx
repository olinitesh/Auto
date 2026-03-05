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
};

type NegotiationSessionDetail = {
  id: string;
  status: string;
  messages: NegotiationMessage[];
};

type WarRoomPageProps = {
  sessionId: string;
  returnTo?: string;
};

const apiBase = "http://localhost:8000";

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

export function WarRoomPage({ sessionId, returnTo }: WarRoomPageProps) {
  const [events, setEvents] = useState<WarRoomEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const wsUrl = useMemo(() => `ws://localhost:8020/ws/negotiations/${sessionId}`, [sessionId]);

  const inboundCount = useMemo(
    () => events.filter((event) => event.event_type.toLowerCase().includes("inbound")).length,
    [events],
  );

  const outboundCount = useMemo(
    () => events.filter((event) => event.event_type.toLowerCase().includes("outbound")).length,
    [events],
  );

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

  function connect() {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => {
      setConnected(false);
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
        </div>
      </section>

      <section className="panel warroom-toolbar">
        <div className="actions warroom-actions">
          <a className="btn" href={returnTo || "/?workspace=offers"}>
            Back To Workspace
          </a>
          <button onClick={connect} className="btn primary" type="button">
            {connected ? "Connected" : "Connect Feed"}
          </button>
          <button onClick={() => void loadHistory()} className="btn" type="button" disabled={loadingHistory}>
            {loadingHistory ? "Loading History..." : "Reload History"}
          </button>
        </div>
      </section>

      {historyError && <p className="error">{historyError}</p>}

      <section className="panel">
        {events.length === 0 ? (
          <p className="empty">No events yet. Queue a round or wait for inbound dealer events.</p>
        ) : (
          <div className="warroom-feed">
            {events.map((event, index) => (
              <article className="warroom-event-card" key={`${event.event_type}-${index}`}>
                <div className="warroom-event-head">
                  <strong>{event.event_type}</strong>
                  <span>{formatEventTime(event.timestamp)}</span>
                </div>
                <pre className="warroom-payload">{JSON.stringify(event.payload ?? {}, null, 2)}</pre>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

