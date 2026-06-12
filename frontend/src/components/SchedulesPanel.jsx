import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Common cron presets so users don't have to remember the syntax.
const PRESETS = [
  { label: "Every minute", cron: "* * * * *" },
  { label: "Every hour", cron: "0 * * * *" },
  { label: "Every day at 9:00 AM", cron: "0 9 * * *" },
  { label: "Every Monday at 8:00 AM", cron: "0 8 * * 1" },
  { label: "First of the month, midnight", cron: "0 0 1 * *" },
  { label: "Custom…", cron: "" },
];

// Modal for viewing and managing scheduled workflow runs.
export default function SchedulesPanel({ workflows, canEdit = true, isSuper = false, onClose }) {
  const [schedules, setSchedules] = useState([]);
  const [wfId, setWfId] = useState("");
  const [preset, setPreset] = useState(PRESETS[2].cron);
  const [cron, setCron] = useState(PRESETS[2].cron);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = () => api.listSchedules().then(setSchedules).catch(() => {});
  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (!wfId && workflows.length) setWfId(workflows[0].id);
  }, [workflows]);

  const onPreset = (value) => {
    setPreset(value);
    if (value !== "") setCron(value); // "" = Custom, keep whatever's typed
  };

  const add = async () => {
    setError("");
    if (!wfId) return setError("Select a saved workflow first (Save it on the canvas).");
    if (!cron.trim()) return setError("Enter a cron expression.");
    setLoading(true);
    try {
      await api.addSchedule(wfId, cron.trim());
      refresh();
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
    } finally {
      setLoading(false);
    }
  };

  const remove = async (jobId) => {
    await api.removeSchedule(jobId);
    refresh();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>🕘 Schedules</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* add new schedule */}
        {canEdit && (
        <div className="sched-add">
          <div className="field">
            <label>Workflow</label>
            <select value={wfId} onChange={(e) => setWfId(e.target.value)}>
              {workflows.length === 0 && <option value="">No saved workflows</option>}
              {workflows.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>When</label>
            <select value={preset} onChange={(e) => onPreset(e.target.value)}>
              {PRESETS.map((p) => (
                <option key={p.label} value={p.cron}>{p.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Cron expression</label>
            <input
              type="text"
              value={cron}
              placeholder="min hour day month weekday"
              onChange={(e) => { setCron(e.target.value); setPreset(""); }}
            />
          </div>
          <button className="btn primary" onClick={add} disabled={loading}>
            {loading ? "Adding…" : "Add schedule"}
          </button>
        </div>
        )}

        {error && <div className="sched-error">{error}</div>}

        {/* existing schedules */}
        <div className="sched-list">
          {schedules.length === 0 && <p className="props-empty">No schedules yet.</p>}
          {schedules.map((s) => (
            <div key={s.job_id} className="sched-row">
              <div>
                <div className="sched-name">{s.name}</div>
                <div className="sched-meta">
                  <code>{s.cron}</code>
                  {s.next_run && <span> · next: {s.next_run}</span>}
                  {isSuper && <span> · 👤 {s.owner}</span>}
                </div>
              </div>
              {canEdit && (
                <button className="btn danger small" onClick={() => remove(s.job_id)}>Remove</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
