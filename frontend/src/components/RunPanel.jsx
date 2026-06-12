import React from "react";

// Bottom panel: run output log.
export default function RunPanel({ logs, running }) {
  return (
    <div className="runpanel">
      <div className="runpanel-head">
        Run Log {running && <span className="spinner">running…</span>}
      </div>
      <div className="runpanel-body">
        {logs.length === 0 && <div className="log-empty">Press “Run” to execute the flow.</div>}
        {logs.map((l, i) => (
          <div key={i} className={`logline level-${l.level}`}>
            <span className="log-ts">{l.ts}</span>
            <span className="log-msg">{l.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
