import React from "react";

// Left sidebar: node types grouped by category, draggable onto the canvas.
export default function Palette({ nodeDefs }) {
  const byCat = {};
  for (const def of nodeDefs) {
    (byCat[def.category] = byCat[def.category] || []).push(def);
  }

  const onDragStart = (e, def) => {
    e.dataTransfer.setData("application/rpa-node", JSON.stringify(def));
    e.dataTransfer.effectAllowed = "move";
  };

  return (
    <aside className="palette">
      <h2>Steps</h2>
      <p className="palette-hint">Drag a step onto the canvas.</p>
      {Object.entries(byCat).map(([cat, defs]) => (
        <div key={cat} className="palette-group">
          <div className="palette-cat">{cat}</div>
          {defs.map((def) => (
            <div
              key={def.type}
              className="palette-item"
              data-category={cat}
              draggable
              onDragStart={(e) => onDragStart(e, def)}
              title={def.description}
            >
              {def.label}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
