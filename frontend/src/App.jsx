import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from "reactflow";

import { api, auth, setUnauthorizedHandler } from "./api.js";
import Palette from "./components/Palette.jsx";
import PropertiesPanel from "./components/PropertiesPanel.jsx";
import RunPanel from "./components/RunPanel.jsx";
import CustomNode from "./components/CustomNode.jsx";
import SchedulesPanel from "./components/SchedulesPanel.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import UsersPanel from "./components/UsersPanel.jsx";
import Login from "./components/Login.jsx";

const ROLE_LEVEL = { viewer: 1, editor: 2, admin: 3, superadmin: 4 };
const atLeast = (user, role) => (ROLE_LEVEL[user?.role] || 0) >= ROLE_LEVEL[role];

let idCounterSeed = 1;
const nextId = () => `n${idCounterSeed++}_${Math.random().toString(36).slice(2, 6)}`;

// Build a one-line summary of a node's most relevant param for the canvas card.
function summarize(def, params) {
  const first = def.params?.[0];
  if (!first) return "";
  const v = params?.[first.name];
  if (v === undefined || v === "" || v === null) return "";
  return String(v).slice(0, 40);
}

function Builder({ user, onLogout }) {
  const canEdit = atLeast(user, "editor");
  const isAdmin = atLeast(user, "admin");
  const isSuper = atLeast(user, "superadmin");
  const [nodeDefs, setNodeDefs] = useState([]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [running, setRunning] = useState(false);
  const [wfName, setWfName] = useState("My Automation");
  const [wfId, setWfId] = useState(null);
  const [workflows, setWorkflows] = useState([]);
  const [showSchedules, setShowSchedules] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showUsers, setShowUsers] = useState(false);

  const wrapperRef = useRef(null);
  const rfInstance = useRef(null);
  const defsByType = useMemo(() => Object.fromEntries(nodeDefs.map((d) => [d.type, d])), [nodeDefs]);
  const nodeTypes = useMemo(() => ({ custom: CustomNode }), []);

  // Load node catalog + saved workflows on mount.
  useEffect(() => {
    api.getNodes().then(setNodeDefs).catch((e) => console.error(e));
    refreshWorkflows();
  }, []);

  const refreshWorkflows = () => api.listWorkflows().then(setWorkflows).catch(() => {});

  const onConnect = useCallback(
    (conn) => setEdges((eds) => addEdge({ ...conn, animated: true }, eds)),
    [setEdges]
  );

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData("application/rpa-node");
      if (!raw) return;
      const def = JSON.parse(raw);
      const pos = rfInstance.current.screenToFlowPosition({ x: e.clientX, y: e.clientY });

      const defaults = {};
      for (const p of def.params) defaults[p.name] = p.default;

      const newNode = {
        id: nextId(),
        type: "custom",
        position: pos,
        data: {
          label: def.label,
          type: def.type,
          category: def.category,
          def,
          params: defaults,
          summary: summarize(def, defaults),
        },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [setNodes]
  );

  const onSelectionChange = useCallback(({ nodes: sel }) => {
    setSelectedId(sel && sel.length ? sel[0].id : null);
  }, []);

  const updateNodeParams = (id, params) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === id
          ? { ...n, data: { ...n.data, params, summary: summarize(n.data.def, params) } }
          : n
      )
    );
  };

  const deleteNode = (id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    setSelectedId(null);
  };

  // Convert canvas state -> backend graph format.
  const toGraph = () => ({
    nodes: nodes.map((n) => ({ id: n.id, type: n.data.type, params: n.data.params, position: n.position })),
    edges: edges.map((e) => ({ source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
  });

  // Run the flow, streaming each log line live over a WebSocket.
  const runFlow = () => {
    setRunning(true);
    setLogs([{ ts: "", level: "info", message: "Starting run…" }]);
    const graph = toGraph();
    const proto = window.location.protocol === "https:" ? "wss" : "ws";

    let opened = false;
    let ws;
    try {
      const tok = encodeURIComponent(auth.token);
      ws = new WebSocket(`${proto}://${window.location.host}/api/run/ws?token=${tok}`);
    } catch {
      restRun(graph);
      return;
    }

    ws.onopen = () => {
      opened = true;
      ws.send(JSON.stringify({ graph, workflow_id: wfId, name: wfName }));
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") {
        setLogs((l) => [...l, msg.entry]);
      } else if (msg.type === "done") {
        setRunning(false);
        ws.close();
      }
    };
    ws.onerror = () => {
      if (!opened) restRun(graph); // socket never connected -> fall back to REST
    };
    ws.onclose = () => setRunning(false);
  };

  // Fallback: one-shot REST run that returns all logs at the end.
  const restRun = async (graph) => {
    try {
      const res = await api.run(graph, wfId, wfName);
      setLogs(res.logs);
    } catch (err) {
      setLogs((l) => [...l, { ts: "", level: "error", message: String(err) }]);
    } finally {
      setRunning(false);
    }
  };

  const saveFlow = async () => {
    const saved = await api.saveWorkflow({ id: wfId, name: wfName, graph: toGraph() });
    setWfId(saved.id);
    refreshWorkflows();
    setLogs((l) => [...l, { ts: "", level: "success", message: `Saved “${saved.name}”.` }]);
  };

  const loadFlow = async (id) => {
    if (!id) return;
    const wf = await api.getWorkflow(id);
    rebuildFromGraph(wf.graph || {});
    setWfId(wf.id);
    setWfName(wf.name);
  };

  const rebuildFromGraph = (graph) => {
    const rebuilt = (graph.nodes || []).map((n) => {
      const def = defsByType[n.type] || { label: n.type, category: "?", params: [], outputs: ["next"] };
      return {
        id: n.id,
        type: "custom",
        position: n.position || { x: 100, y: 100 },
        data: {
          label: def.label,
          type: n.type,
          category: def.category,
          def,
          params: n.params || {},
          summary: summarize(def, n.params || {}),
        },
      };
    });
    setNodes(rebuilt);
    setEdges(
      (graph.edges || []).map((e, i) => ({
        id: `e${i}`,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        animated: true,
      }))
    );
  };

  const newFlow = () => {
    setNodes([]);
    setEdges([]);
    setWfId(null);
    setWfName("My Automation");
    setLogs([]);
  };

  const selectedNode = nodes.find((n) => n.id === selectedId) || null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">⚙️ RPA Builder</div>
        <input
          className="wf-name"
          value={wfName}
          onChange={(e) => setWfName(e.target.value)}
          disabled={!canEdit}
        />
        {canEdit && <button className="btn" onClick={newFlow}>New</button>}
        {canEdit && <button className="btn" onClick={saveFlow}>Save</button>}
        <select className="wf-select" value="" onChange={(e) => loadFlow(e.target.value)}>
          <option value="">Open…</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>
              {isSuper ? `${w.name}  ·  ${w.owner}` : w.name}
            </option>
          ))}
        </select>
        <button className="btn" onClick={() => setShowSchedules(true)}>🕘 Schedules</button>
        <button className="btn" onClick={() => setShowHistory(true)}>📜 History</button>
        {isAdmin && <button className="btn" onClick={() => setShowUsers(true)}>👥 Users</button>}
        {canEdit && (
          <button className="btn primary" onClick={runFlow} disabled={running}>
            {running ? "Running…" : "▶ Run"}
          </button>
        )}
        <div className="topbar-user">
          <span className="user-chip" title={`Role: ${user.role}`}>
            {user.username} <span className="role-pill">{user.role}</span>
          </span>
          <button className="btn" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      {showSchedules && (
        <SchedulesPanel
          workflows={workflows}
          canEdit={canEdit}
          isSuper={isSuper}
          onClose={() => setShowSchedules(false)}
        />
      )}
      {showHistory && <HistoryPanel isSuper={isSuper} onClose={() => setShowHistory(false)} />}
      {showUsers && <UsersPanel currentUser={user} onClose={() => setShowUsers(false)} />}

      <div className="workspace">
        <Palette nodeDefs={nodeDefs} />

        <div className="canvas-wrap" ref={wrapperRef} onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={(inst) => (rfInstance.current = inst)}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background gap={16} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
          <RunPanel logs={logs} running={running} />
        </div>

        <PropertiesPanel node={selectedNode} onChange={updateNodeParams} onDelete={deleteNode} />
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  // On load, if we have a stored token, validate it by fetching the current user.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    if (auth.token) {
      api.me().then(setUser).catch(() => { auth.token = ""; }).finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  const logout = () => {
    auth.token = "";
    setUser(null);
  };

  if (checking) return <div className="login-screen"><div className="login-sub">Loading…</div></div>;
  if (!user) return <Login onLogin={setUser} />;

  return (
    <ReactFlowProvider>
      <Builder user={user} onLogout={logout} />
    </ReactFlowProvider>
  );
}
