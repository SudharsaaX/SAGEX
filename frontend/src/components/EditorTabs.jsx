import React from "react";

export default function EditorTabs({
  files = [],
  active,
  dirtyFiles = {},
  onOpenFile,
  onCloseFile,
}) {
  return (
    <div className="tabs">

      {files.map((file) => {
        const name = file.split(/[\\/]/).pop();
        const activeTab = file === active;
        const dirty = Boolean(dirtyFiles[file]);

        return (
          <div
            key={file}
            className={`tab ${activeTab ? "active" : ""}`}
            onClick={() => onOpenFile(file)}
          >
            <span className="tab-name">
              {dirty && (
                <span className="dirty-dot">●</span>
              )}

              {name}
            </span>

            <button
              type="button"
              className="close"
              title={`Close ${name}`}
              onClick={(event) => {
                event.stopPropagation();
                onCloseFile(file);
              }}
            >
              ×
            </button>
          </div>
        );
      })}

      <div
        className="tab new"
        title="New file"
      >
        +
      </div>

    </div>
  );
}