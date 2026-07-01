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
        color: new vscode.ThemeColor("editorCodeLens.foreground"),
        textDecoration: "none; display: block; opacity: 0.85;",
      },
    });
  }

  setDecoration(line: number, text: string): void {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      return;
    }
    this._activeEditor = editor;
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
