import React, { useEffect, useState } from "react";
import WorkspaceSidebar from "./WorkspaceSidebar";
import EditorArea from "./EditorArea";
import AgentPanel from "./AgentPanel";
import StatusBar from "./StatusBar";
import api from "../api";
import "../styles.css";

export default function AppShell() {
  const [workspace, setWorkspace] = useState(
    () => localStorage.getItem("sagex.workspace") || null,
  );

  const [files, setFiles] = useState([]);
  const [openFiles, setOpenFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);

  const [fileContents, setFileContents] = useState({});
  const [dirtyFiles, setDirtyFiles] = useState({});

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const [connection, setConnection] = useState("Idle");

  const [leftWidth, setLeftWidth] = useState(250);
  const [rightWidth, setRightWidth] = useState(360);

  useEffect(() => {
    if (workspace) {
      selectWorkspace(workspace);
    }
  }, []);

  async function selectWorkspace(path) {
    if (!path) return;

    try {
      setConnection("Connecting");

      const res = await api.setWorkspace(path);

      if (!res?.project) {
        setConnection("Error");
        return;
      }

      setWorkspace(res.project);
      localStorage.setItem("sagex.workspace", res.project);

      await loadFiles();

      setConnection("Connected");
    } catch (error) {
      console.error("Workspace error:", error);
      setConnection("Offline");
    }
  }

  async function loadFiles() {
    try {
      const res = await api.getFiles();
      setFiles(res?.files || []);
    } catch (error) {
      console.error("Failed to load files:", error);
    }
  }

  async function openFile(path) {
    if (!path) return;

    if (!openFiles.includes(path)) {
      setOpenFiles((current) => [...current, path]);
    }

    setActiveFile(path);

    if (!fileContents[path]) {
      try {
        const res = await api.getFile(path);

        setFileContents((current) => ({
          ...current,
          [path]: res?.content || "",
        }));
      } catch (error) {
        console.error("Failed to open file:", error);
      }
    }
  }

  function closeFile(path) {
    const nextFiles = openFiles.filter((file) => file !== path);

    setOpenFiles(nextFiles);

    setDirtyFiles((current) => {
      const next = { ...current };
      delete next[path];
      return next;
    });

    if (activeFile === path) {
      setActiveFile(nextFiles[nextFiles.length - 1] || null);
    }
  }

  function updateFileContent(path, content) {
    setFileContents((current) => ({
      ...current,
      [path]: content,
    }));

    setDirtyFiles((current) => ({
      ...current,
      [path]: true,
    }));
  }

  function startDragLeft(event) {
    event.preventDefault();

    const startX = event.clientX;
    const startWidth = leftWidth;

    function onMove(e) {
      const delta = e.clientX - startX;
      const nextWidth = Math.max(180, Math.min(500, startWidth + delta));

      setLeftWidth(nextWidth);
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function startDragRight(event) {
    event.preventDefault();

    const startX = event.clientX;
    const startWidth = rightWidth;

    function onMove(e) {
      const delta = startX - e.clientX;

      const nextWidth = Math.max(280, Math.min(600, startWidth + delta));

      setRightWidth(nextWidth);
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return (
    <div className="shell">
      {/* TOP BAR */}
      <div className="titlebar">
        <div className="window-controls" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="titlebar-title">SAGE-X</div>

        <div className="titlebar-status">{connection}</div>
      </div>

      {/* MAIN IDE */}
      <div className="main-split">
        {/* LEFT EXPLORER */}
        {!leftCollapsed ? (
          <>
            <div
              style={{
                width: leftWidth,
                minWidth: 180,
                maxWidth: 500,
                display: "flex",
                flexDirection: "column",
              }}
            >
              <WorkspaceSidebar
                workspace={workspace}
                files={files}
                activeFile={activeFile}
                onSelectWorkspace={selectWorkspace}
                onOpenFile={openFile}
                onCollapse={() => setLeftCollapsed(true)}
              />
            </div>

            <div className="gutter" onMouseDown={startDragLeft} />
          </>
        ) : (
          <button
            className="rail-toggle left-rail"
            onClick={() => setLeftCollapsed(false)}
            title="Show Explorer"
          >
            EXPLORER
          </button>
        )}

        {/* EDITOR */}
        <div
          style={{
            flex: 1,
            minWidth: 300,
            minHeight: 0,
            display: "flex",
          }}
        >
          <EditorArea
            openFiles={openFiles}
            activeFile={activeFile}
            fileContents={fileContents}
            dirtyFiles={dirtyFiles}
            onOpenFile={openFile}
            onCloseFile={closeFile}
            onChangeFile={updateFileContent}
          />
        </div>

        {/* RIGHT AGENT */}
        {!rightCollapsed && (
          <div className="gutter" onMouseDown={startDragRight} />
        )}

        {!rightCollapsed ? (
          <div
            style={{
              width: rightWidth,
              minWidth: 280,
              maxWidth: 600,
              height: "100%",
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <AgentPanel
              workspace={workspace}
              onCollapse={() => setRightCollapsed(true)}
              onFilesChanged={loadFiles}
            />
          </div>
        ) : (
          <button
            className="rail-toggle right-rail"
            onClick={() => setRightCollapsed(false)}
            title="Show SAGE-X Agent"
          >
            SAGE-X
          </button>
        )}
      </div>

      {/* BOTTOM STATUS */}
      <StatusBar
        workspace={workspace}
        activeFile={activeFile}
        connection={connection}
        dirty={Boolean(dirtyFiles[activeFile])}
      />
    </div>
  );
}
