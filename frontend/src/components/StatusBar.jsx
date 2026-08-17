import React from "react";

export default function StatusBar({
  workspace,
  activeFile,
  connection,
  dirty,
}) {
  return (
    <div className="statusbar">
      <div className="left">
        {workspace || "(no workspace)"}
      </div>

      <div className="center">
        {activeFile || "No file"}
        {dirty && " ●"}
      </div>

      <div className="right">
        {connection === "Connected" ? "● " : "○ "}
        Qwen2.5-Coder 7B · Local
      </div>
    </div>
  );
}