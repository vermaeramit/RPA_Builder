import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// Admin-only modal to manage users and their roles.
export default function UsersPanel({ currentUser, onClose }) {
  // Only a superadmin can grant the superadmin role.
  const ROLES =
    currentUser.role === "superadmin"
      ? ["viewer", "editor", "admin", "superadmin"]
      : ["viewer", "editor", "admin"];
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("viewer");
  const [error, setError] = useState("");

  const refresh = () => api.listUsers().then(setUsers).catch((e) => setError(String(e)));
  useEffect(() => { refresh(); }, []);

  const add = async () => {
    setError("");
    if (!username || !password) return setError("Username and password are required.");
    try {
      await api.createUser(username, password, role);
      setUsername("");
      setPassword("");
      setRole("viewer");
      refresh();
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
    }
  };

  const changeRole = async (id, newRole) => {
    await api.setUserRole(id, newRole);
    refresh();
  };

  const remove = async (id) => {
    try {
      await api.deleteUser(id);
      refresh();
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>👥 Users</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="sched-add">
          <div className="field">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="field">
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <button className="btn primary" onClick={add}>Add user</button>
        </div>

        {error && <div className="sched-error">{error}</div>}

        <div className="sched-list">
          {users.map((u) => (
            <div key={u.id} className="sched-row">
              <div>
                <div className="sched-name">
                  {u.username}{u.id === currentUser.id && <span className="you-tag"> (you)</span>}
                </div>
                <div className="sched-meta">role: {u.role}</div>
              </div>
              <div className="user-actions">
                <select
                  value={u.role}
                  onChange={(e) => changeRole(u.id, e.target.value)}
                  disabled={u.id === currentUser.id}
                  title={u.id === currentUser.id ? "You can't change your own role" : ""}
                >
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
                <button
                  className="btn danger small"
                  onClick={() => remove(u.id)}
                  disabled={u.id === currentUser.id}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
