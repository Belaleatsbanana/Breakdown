import * as vscode from "vscode";
import type { StripDecorator } from "./inline_strip_manager";

export class DecorationHostAdapter implements StripDecorator {
  private readonly _decorationType: vscode.TextEditorDecorationType;

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
    const zeroBasedLine = Math.min(Math.max(line - 1, 0), editor.document.lineCount - 1);
    const lineRange = editor.document.lineAt(zeroBasedLine).range;
    editor.setDecorations(this._decorationType, [
      { range: lineRange, renderOptions: { after: { contentText: `  ${text}` } } },
    ]);
  }

  clearDecoration(): void {
    vscode.window.activeTextEditor?.setDecorations(this._decorationType, []);
  }

  dispose(): void {
    this._decorationType.dispose();
  }
}
