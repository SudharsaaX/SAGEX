import React, { useEffect, useState } from "react";
import api from "../api";

function ChatTab({ onFilesChanged }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    const command = input.trim();

    if (!command || sending) return;

    setMessages((current) => [
      ...current,
      {
        role: "user",
        text: command,
      },
    ]);

    setInput("");
    setSending(true);

    try {
      const res = await api.sendCommand(command);

      if (res?.error) {
        throw new Error(res.error);
      }

      const text = res?.response ?? "SAGE-X returned an empty response.";

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: String(text),
        },
      ]);

      const match = /(?:\/approve\/)([\w-]+)/.exec(String(text));

      if (match) {
        setMessages((current) => [
          ...current,
          {
            role: "proposal",
            changeId: match[1],
          },
        ]);
      }

      if (onFilesChanged) {
        onFilesChanged();
      }
    } catch (error) {
      console.error("SAGE-X command failed:", error);

      setMessages((current) => [
        ...current,
        {
          role: "error",
          text: `SAGE-X error: ${error.message}`,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    send();
  }

  async function approve(changeId) {
    try {
      const res = await api.approve(changeId);

      if (res?.error) {
        throw new Error(res.error);
      }

      setMessages((current) => [
        ...current,
        {
          role: "system",
          text: `Change ${changeId} approved and applied.`,
        },
      ]);

      if (onFilesChanged) {
        onFilesChanged();
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "error",
          text: `Approval failed: ${error.message}`,
        },
      ]);
    }
  }

  return (
    <div className="agent-chat">
      <div className="agent-header">
        <div className="agent-title">SAGE-X</div>

        <div className="agent-sub">Qwen2.5-Coder 7B · Local</div>
      </div>

      <div className="chat-area">
        {messages.length === 0 && (
          <div className="msg assistant">
            Ask SAGE-X to inspect, explain, search, or propose a change to your
            project.
          </div>
        )}

        {messages.map((message, index) => {
          if (message.role === "proposal") {
            return (
              <div key={index} className="msg assistant">
                <div className="proposal-card">
                  <div className="proposal-title">CHANGE PROPOSAL</div>

                  <div className="proposal-id">{message.changeId}</div>

                  <div className="proposal-actions">
                    <button onClick={() => approve(message.changeId)}>
                      Approve
                    </button>
                  </div>
                </div>
              </div>
            );
          }

          return (
            <div key={index} className={`msg ${message.role}`}>
              <pre>{message.text}</pre>
            </div>
          );
        })}

        {sending && (
          <div className="msg assistant">
            <pre>SAGE-X is thinking...</pre>
          </div>
        )}
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask SAGE-X..."
          disabled={sending}
        />

        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}

function HistoryTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setLoading(true);

      const res = await api.getHistory(50);

      setItems(res?.history || []);
    } catch (error) {
      console.error("History error:", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="agent-history">
      {loading ? (
        <div className="empty">Loading history...</div>
      ) : items.length === 0 ? (
        <div className="empty">No changes yet.</div>
      ) : (
        <div className="history-list">
          {items
            .slice()
            .reverse()
            .map((item) => (
              <div key={item.history_id} className="history-item">
                <div className="h-meta">
                  {item.summary || item.user_request}
                </div>

                <div className="h-files">
                  {item.file_path} · {item.status}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

export default function AgentPanel({ workspace, onFilesChanged }) {
  const [tab, setTab] = useState("chat");

  return (
    <aside className="sidebar right">
      <div className="agent-nav">
        <button
          className={tab === "chat" ? "active" : ""}
          onClick={() => setTab("chat")}
        >
          CHAT
        </button>

        <button
          className={tab === "history" ? "active" : ""}
          onClick={() => setTab("history")}
        >
          HISTORY
        </button>
      </div>

      <div className="agent-body">
        <div
          style={{
            display: tab === "chat" ? "block" : "none",
            height: "100%",
          }}
        >
          <ChatTab workspace={workspace} onFilesChanged={onFilesChanged} />
        </div>

        <div
          style={{
            display: tab === "history" ? "block" : "none",
            height: "100%",
          }}
        >
          <HistoryTab />
        </div>
      </div>
    </aside>
  );
}
