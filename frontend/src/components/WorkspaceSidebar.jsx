import React, { useState, useMemo } from "react";
import api from "../api";

function buildTree(paths) {
  const root = {
    name: "",
    children: {},
  };

  for (const path of paths) {
    const parts = path.split(/[\\/]/);

    let node = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];

      if (!node.children[part]) {
        node.children[part] = {
          name: part,
          children: {},
          isFile: i === parts.length - 1,
        };
      }

      node = node.children[part];
    }
  }

  return root;
}

function TreeNode({ node, path, onOpenFile, activeFile }) {
  const [open, setOpen] = useState(false);

  const isFile = node.isFile;
  const children = Object.values(node.children || {});

  const isActive = isFile && path === activeFile;

  return (
    <div className="tree-node">
      <div
        className={`tree-label ${
          isFile ? "file" : "folder"
        } ${isActive ? "active" : ""}`}
        onClick={() => {
          if (isFile) {
            onOpenFile(path);
          } else {
            setOpen((current) => !current);
          }
        }}
      >
        {!isFile && (
          <span className={`caret ${open ? "open" : ""}`}>
            {open ? "▾" : "▸"}
          </span>
        )}

        {isFile && <span className="file-icon">{getFileIcon(node.name)}</span>}

        <span className="name">{node.name}</span>
      </div>

      {!isFile && open && (
        <div className="children">
          {children.map((child) => (
            <TreeNode
              key={child.name}
              node={child}
              path={path ? `${path}/${child.name}` : child.name}
              onOpenFile={onOpenFile}
              activeFile={activeFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function getFileIcon(name) {
  const extension = name.split(".").pop().toLowerCase();

  if (extension === "py") return "PY";
  if (extension === "js" || extension === "jsx") return "JS";
  if (extension === "ts" || extension === "tsx") return "TS";
  if (extension === "css") return "#";
  if (extension === "html") return "H";
  if (extension === "json") return "{}";
  if (extension === "md") return "M";

  return "·";
}

export default function WorkspaceSidebar({
  workspace,
  files,
  activeFile,
  onSelectWorkspace,
  onOpenFile,
}) {
  const tree = useMemo(() => buildTree(files || []), [files]);

  async function handlePick() {
    try {
      const res = await api.pickWorkspace();

      if (res?.path) {
        await onSelectWorkspace(res.path);
        return;
      }

      const manual = window.prompt("Enter workspace path:");

      if (manual) {
        await onSelectWorkspace(manual);
      }
    } catch (error) {
      console.error("Workspace picker failed:", error);

      const manual = window.prompt("Enter workspace path:");

      if (manual) {
        await onSelectWorkspace(manual);
      }
    }
  }

  return (
    <aside className="sidebar left">
      <div className="brand">
        <div className="logo">SAGE-X</div>

        <div className="workspace-meta">
          <div className="project-name">{workspace || "(no workspace)"}</div>
        </div>
      </div>

      <div className="explorer">
        <div className="explorer-header">EXPLORER</div>

        <div className="explorer-tree">
          {Object.values(tree.children).map((child) => (
            <TreeNode
              key={child.name}
              node={child}
              path={child.name}
              onOpenFile={onOpenFile}
              activeFile={activeFile}
            />
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="change-workspace-btn" onClick={handlePick}>
          Change Workspace
        </button>
      </div>
    </aside>
  );
}
