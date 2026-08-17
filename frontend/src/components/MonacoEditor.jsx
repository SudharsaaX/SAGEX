import React, { useEffect, useRef } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";

export default function MonacoEditor({
  path,
  content = "",
  onChange,
}) {
  const monaco = useMonaco();
  const editorRef = useRef(null);

  function handleMount(editor) {
    editorRef.current = editor;
  }

  useEffect(() => {
    if (!monaco || !editorRef.current || !path) return;

    const extension = path
      .split(/[\\/]/)
      .pop()
      .split(".")
      .pop()
      .toLowerCase();

    let language = "plaintext";

    if (extension === "js" || extension === "jsx") {
      language = "javascript";
    } else if (extension === "ts" || extension === "tsx") {
      language = "typescript";
    } else if (extension === "py") {
      language = "python";
    } else if (extension === "json") {
      language = "json";
    } else if (extension === "css") {
      language = "css";
    } else if (extension === "html") {
      language = "html";
    } else if (extension === "md") {
      language = "markdown";
    }

    const model = editorRef.current.getModel();

    if (model) {
      monaco.editor.setModelLanguage(model, language);
    }
  }, [monaco, path]);

  return (
    <Editor
      height="100%"
      width="100%"
      language="plaintext"
      value={content}
      onMount={handleMount}
      onChange={(value) => {
        if (onChange) {
          onChange(value ?? "");
        }
      }}
      theme="vs-dark"
      options={{
        minimap: {
          enabled: false,
        },

        automaticLayout: true,

        fontSize: 13,
        lineHeight: 21,

        padding: {
          top: 12,
          bottom: 12,
        },

        smoothScrolling: true,

        scrollBeyondLastLine: false,

        renderWhitespace: "selection",

        cursorBlinking: "smooth",

        bracketPairColorization: {
          enabled: true,
        },

        folding: true,

        wordWrap: "off",

        overviewRulerBorder: false,

        scrollbar: {
          verticalScrollbarSize: 8,
          horizontalScrollbarSize: 8,
        },
      }}
    />
  );
}