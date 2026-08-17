import React, { useState } from "react";
import EditorTabs from "./EditorTabs";
import MonacoEditor from "./MonacoEditor";
import TerminalPanel from "./TerminalPanel";

export default function EditorArea({
  openFiles = [],
  activeFile,
  fileContents = {},
  dirtyFiles = {},
  onOpenFile,
  onCloseFile,
  onChangeFile,
}) {
  const [terminalHeight, setTerminalHeight] = useState(180);

  const activeContent = activeFile
    ? fileContents[activeFile] || ""
    : "";

  function startTerminalResize(event) {
    event.preventDefault();

    const startY = event.clientY;
    const startHeight = terminalHeight;

    function onMove(e) {
      const delta = startY - e.clientY;

      const nextHeight = Math.max(
        100,
        Math.min(450, startHeight + delta)
      );

      setTerminalHeight(nextHeight);
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div className="editor-area">

      <EditorTabs
        files={openFiles}
        active={activeFile}
        dirtyFiles={dirtyFiles}
        onOpenFile={onOpenFile}
        onCloseFile={onCloseFile}
      />

      <div className="editor-and-terminal">

        <div className="editor-panel">
          {activeFile ? (
            <MonacoEditor
              path={activeFile}
              content={activeContent}
              onChange={(content) =>
                onChangeFile(activeFile, content)
              }
            />
          ) : (
            <div className="empty">
              Open a file to begin
            </div>
          )}
        </div>

        <div
          className="gutter horizontal"
          onMouseDown={startTerminalResize}
        />

        <div
          className="terminal-container"
          style={{ height: terminalHeight }}
        >
          <TerminalPanel />
        </div>

      </div>

    </div>
  );
}