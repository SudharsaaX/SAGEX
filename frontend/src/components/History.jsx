import React, { useEffect, useState } from "react";
import api from "../api";

export default function History() {
  const [items, setItems] = useState([]);

  async function load() {
    const res = await api.getHistory(50);
    setItems(res?.history || []);
  }

  useEffect(() => { load(); }, []);

  const approve = async (changeId) => {
    await api.approve(changeId);
    load();
  };

  return (
    <section className="panel">
      <h2>History</h2>
      <button onClick={load}>Refresh</button>
      <ul className="history-list">
        {items.map((h) => (
          <li key={h.history_id}>
            <div className="meta">
              <strong>{h.change_id}</strong> — {h.file_path} — {h.status}
            </div>
            <div className="content">{h.summary || JSON.stringify(h)}</div>
            {h.change_id && h.status !== "APPLIED" && (
              <button onClick={() => approve(h.change_id)}>Approve</button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
