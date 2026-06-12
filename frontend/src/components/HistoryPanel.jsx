import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Modal for browsing past runs and inspecting a run's full log.
export default function HistoryPanel({ isSuper = false, onClose }) {
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null); // full run detail

  useEffect(() => {
    api.listRuns(50).then(setRuns).catch(() => {});
  }, []);

  const open = async (id) => {
    const r = await api.getRun(id);
    setSelected(r);
  };

  const fmt = (iso) => (iso ? iso.replace("T", " ").slice(0, 19) : "—");

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>📜 Run History</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="history-layout">
          {/* list of runs */}
          <div className="history-list">
            {runs.length === 0 && <p className="props-empty">No runs yet.</p>}
            {runs.map((r) => (
              <div
                key={r.id}
                className={`history-row ${selected?.id === r.id ? "active" : ""}`}
                onClick={() => open(r.id)}
              >
                <span className={`status-dot ${r.status}`} />
                <div className="history-row-main">
                  <div className="history-name">{r.workflow_name}</div>
                  <div className="history-meta">
                    {fmt(r.started)} · {r.duration_ms} ms · {r.trigger}
                    {isSuper && <> · 👤 {r.owner}</>}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* selected run's log */}
          <div className="history-detail">
            {!selected && <p className="props-empty">Select a run to view its log.</p>}
            {selected && (
              <>
                <div className="history-detail-head">
                  <span className={`status-badge ${selected.status}`}>{selected.status}</span>
                  <span>{selected.workflow_name}</span>
                  <span className="history-meta">{selected.duration_ms} ms</span>
                </div>
                <div className="history-log">
                  {selected.logs.map((l, i) => (
                    <div key={i} className={`logline level-${l.level}`}>
                      <span className="log-ts">{l.ts}</span>
                      <span className="log-msg">{l.message}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
