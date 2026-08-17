import React, { useState } from "react";
import api from "../api";

export default function Command() {
  const [cmd, setCmd] = useState("");
  const [response, setResponse] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!cmd) return;
    const res = await api.sendCommand(cmd);
    setResponse(res?.response || JSON.stringify(res));
  };

  return (
    <section className="panel">
      <h2>Command</h2>
      <form onSubmit={submit}>
        <input
          placeholder="Enter command for agent"
          value={cmd}
          onChange={(e) => setCmd(e.target.value)}
        />
        <button type="submit">Send</button>
      </form>
      {response && (
        <pre className="response">{typeof response === "string" ? response : JSON.stringify(response, null, 2)}</pre>
      )}
    </section>
  );
}
