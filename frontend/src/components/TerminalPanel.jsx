import React, { useEffect, useRef, useState } from "react";
import api from "../api";

export default function TerminalPanel() {
  const [lines, setLines] = useState([
    "$ SAGE-X terminal — ready",
  ]);

  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [cwd, setCwd] = useState("");

  const bodyRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop =
        bodyRef.current.scrollHeight;
    }
  }, [lines]);

  async function submit(event) {
    event.preventDefault();

    const command = input.trim();

    if (!command || running) return;

    if (command === "clear") {
      setLines([]);
      setInput("");
      return;
    }

    setLines((current) => [
      ...current,
      `$ ${command}`,
    ]);

    setInput("");
    setRunning(true);

    try {
      const result = await api.executeTerminal(command);

      if (result.error) {
        throw new Error(result.error);
      }

      if (result.cwd) {
        setCwd(result.cwd);
      }

      if (result.output) {
        setLines((current) => [
          ...current,
          result.output,
        ]);
      }
    } catch (error) {
      setLines((current) => [
        ...current,
        `Terminal error: ${error.message}`,
      ]);
    } finally {
      setRunning(false);

      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  }

  function handleKeyDown(event) {
    if (event.ctrlKey && event.key.toLowerCase() === "l") {
      event.preventDefault();
      setLines([]);
    }
  }

  return (
    <div className="terminal">

      <div className="terminal-header">
        <span>TERMINAL</span>

        {cwd && (
          <span className="terminal-cwd">
            {cwd}
          </span>
        )}
      </div>

      <div
        ref={bodyRef}
        className="terminal-body"
      >
        {lines.map((line, index) => (
          <div
            key={index}
            className="term-line"
          >
            {line}
          </div>
        ))}

        {running && (
          <div className="term-line">
            Running...
          </div>
        )}
      </div>

      <form
        className="terminal-input"
        onSubmit={submit}
      >
        <span className="terminal-prompt">
          $
        </span>

        <input
          ref={inputRef}
          value={input}
          onChange={(event) =>
            setInput(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder="Type a command..."
          disabled={running}
          spellCheck={false}
        />
      </form>

    </div>
  );
}