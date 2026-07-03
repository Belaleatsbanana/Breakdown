import * as vscode from "vscode";
import type { StripDecorator } from "./inline_strip_manager";

export class DecorationHostAdapter implements StripDecorator {
  private readonly _decorationType: vscode.TextEditorDecorationType;
  private _activeEditor: vscode.TextEditor | null = null;

  constructor() {
    this._decorationType = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      after: {
        margin: "0 0 0 1em",
        color: new vscode.ThemeColor("editorInfo.foreground"),
        backgroundColor: new vscode.ThemeColor("editorInfo.background"),
        // Deliberately inline (no display:block) — a block box here isn't
        // given its own row by the editor's line grid, so it just overlaps
        // whatever is rendered on the line below instead of pushing it down.
        textDecoration: "none; padding: 0 0.4em; border-radius: 3px;",
      },
    });
  }

  setDecoration(line: number, text: string): void {
    if (!this._activeEditor) {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }
      this._activeEditor = editor;
    }
    const editor = this._activeEditor;
    const zeroBasedLine = Math.min(Math.max(line - 1, 0), editor.document.lineCount - 1);
    const lineRange = editor.document.lineAt(zeroBasedLine).range;
    editor.setDecorations(this._decorationType, [
      { range: lineRange, renderOptions: { after: { contentText: `  ${text}` } } },
    ]);
  }

  clearDecoration(): void {
    if (this._activeEditor) {
      this._activeEditor.setDecorations(this._decorationType, []);
      this._activeEditor = null;
    }
  }

  dispose(): void {
    this._decorationType.dispose();
  }
}
