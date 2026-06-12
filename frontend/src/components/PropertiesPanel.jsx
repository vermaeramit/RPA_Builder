import React from "react";

// Right sidebar: edit the selected node's parameters.
export default function PropertiesPanel({ node, onChange, onDelete }) {
  if (!node) {
    return (
      <aside className="props">
        <h2>Properties</h2>
        <p className="props-empty">Select a step to edit its settings.</p>
      </aside>
    );
  }

  const def = node.data.def;
  const params = node.data.params || {};

  const update = (name, value) => {
    onChange(node.id, { ...params, [name]: value });
  };

  return (
    <aside className="props">
      <h2>{node.data.label}</h2>
      <p className="props-desc">{def.description}</p>

      {def.params.length === 0 && <p className="props-empty">No settings for this step.</p>}

      {def.params.map((p) => (
        <div key={p.name} className="field">
          <label>{p.label}</label>
          {renderField(p, params[p.name], (v) => update(p.name, v))}
        </div>
      ))}

      <button className="btn danger" onClick={() => onDelete(node.id)}>
        Delete step
      </button>
    </aside>
  );
}

function renderField(p, value, onChange) {
  const v = value ?? p.default ?? "";
  switch (p.type) {
    case "text":
      return <textarea value={v} placeholder={p.placeholder} onChange={(e) => onChange(e.target.value)} />;
    case "number":
      return <input type="number" value={v} onChange={(e) => onChange(e.target.value)} />;
    case "bool":
      return (
        <input
          type="checkbox"
          checked={v === true || v === "true"}
          onChange={(e) => onChange(e.target.checked)}
        />
      );
    case "select":
      return (
        <select value={v} onChange={(e) => onChange(e.target.value)}>
          {p.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
    default:
      return <input type="text" value={v} placeholder={p.placeholder} onChange={(e) => onChange(e.target.value)} />;
  }
}
