import type { CSSProperties } from "react";
import { useMemo, useState } from "react";

type WarRoomEvent = {
  event_type: string;
  session_id?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
};

type WarRoomPageProps = {
  sessionId: string;
};

export function WarRoomPage({ sessionId }: WarRoomPageProps) {
  const [events, setEvents] = useState<WarRoomEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsUrl = useMemo(() => `ws://localhost:8020/ws/negotiations/${sessionId}`, [sessionId]);

  function connect() {
    const socket = new WebSocket(wsUrl);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
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
    <div style={styles.container}>
      <h1 style={styles.title}>AutoHaggle War Room</h1>
      <p style={styles.meta}>Session: {sessionId}</p>
      <button onClick={connect} style={styles.button}>
        {connected ? "Connected" : "Connect Feed"}
      </button>
      <div style={styles.feed}>
        {events.length === 0 && <p style={styles.empty}>No events yet. Start a negotiation and queue a round.</p>}
        {events.map((event, index) => (
          <div key={`${event.event_type}-${index}`} style={styles.card}>
            <div style={styles.row}>
              <strong>{event.event_type}</strong>
              <span>{event.timestamp ?? "live"}</span>
            </div>
            <pre style={styles.pre}>{JSON.stringify(event.payload ?? {}, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
    maxWidth: "900px",
    margin: "32px auto",
    padding: "0 16px",
  },
  title: { marginBottom: "4px" },
  meta: { color: "#555", marginTop: 0 },
  button: {
    border: "1px solid #222",
    background: "#f5f5f5",
    padding: "8px 12px",
    cursor: "pointer",
    borderRadius: "8px",
    marginBottom: "14px",
  },
  feed: { display: "grid", gap: "10px" },
  empty: { color: "#666" },
  card: {
    border: "1px solid #ddd",
    borderRadius: "10px",
    padding: "10px",
    background: "#fff",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    marginBottom: "6px",
    fontSize: "14px",
  },
  pre: {
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: "12px",
    color: "#333",
  },
};
