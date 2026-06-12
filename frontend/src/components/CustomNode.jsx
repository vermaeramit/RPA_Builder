import React from "react";
import { Handle, Position } from "reactflow";

// One visual node on the canvas. data = { label, type, category, params, def }
export default function CustomNode({ data, selected }) {
  const outputs = data.def?.outputs || ["next"];
  const isStart = data.type === "control.start";

  return (
    <div className={`rpa-node ${selected ? "selected" : ""}`} data-category={data.category}>
      {/* input handle (start node has none) */}
      {!isStart && <Handle type="target" position={Position.Top} className="rpa-handle" />}

      <div className="rpa-node-head">
        <span className="rpa-node-cat">{data.category}</span>
        <span className="rpa-node-title">{data.label}</span>
      </div>

      {/* a short summary of the most relevant param, if set */}
      {data.summary ? <div className="rpa-node-body">{data.summary}</div> : null}

      {/* output handles */}
      {outputs.length === 1 ? (
        <Handle type="source" position={Position.Bottom} id={outputs[0]} className="rpa-handle" />
      ) : (
        <div className="rpa-out-row">
          {outputs.map((o, i) => (
            <div key={o} className="rpa-out">
              <Handle
                type="source"
                position={Position.Bottom}
                id={o}
                className="rpa-handle"
                style={{ left: `${((i + 1) / (outputs.length + 1)) * 100}%` }}
              />
              <span className="rpa-out-label" style={{ left: `${((i + 1) / (outputs.length + 1)) * 100}%` }}>
                {o}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
