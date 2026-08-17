import React, { useState } from "react";

export default function TerminalPanel() {
  const [lines, setLines] = useState(["$ SAGE-X terminal (local) — ready"]);
  const [input, setInput] = useState("");

  function submit(e) {
    e.preventDefault();
    if (!input) return;
    setLines((l) => [...l, `> ${input}`, `command not connected (dev)`]);
    setInput("");
  }

  return (
    <div className="terminal">
      <div className="terminal-header">TERMINAL</div>
      <div className="terminal-body">
        {lines.map((ln, i) => (
          <div key={i} className="term-line">{ln}</div>
        ))}
      </div>
      <form className="terminal-input" onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type a command" />
      </form>
    </div>
  );
}
