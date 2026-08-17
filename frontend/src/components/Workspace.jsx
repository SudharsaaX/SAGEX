import React, { useState } from "react";

export default function Workspace({ onSetWorkspace, current }) {
  const [path, setPath] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (path) onSetWorkspace(path);
  };

  return (
    <section className="panel">
      <h2>Workspace</h2>
      <form onSubmit={submit}>
        <input
          placeholder="project path (e.g. d:/SAGE-X/SAGEX)"
          value={path}
          onChange={(e) => setPath(e.target.value)}
        />
        <button type="submit">Set Workspace</button>
      </form>
      <div className="note">Current: {current || "(not set)"}</div>
    </section>
  );
}
