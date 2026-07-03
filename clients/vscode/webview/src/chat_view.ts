// clients/vscode/webview/src/chat_view.ts
import { marked } from "marked";

export class ChatView {
  constructor(private readonly _container: HTMLElement) {}

  addExplainTurn(file: string, line: number, text: string): void {
    this._append(`**${file}:${line}**\n\n${text}`);
  }

  addAskTurn(question: string, text: string): void {
    this._append(`**Q: ${question}**\n\n${text}`);
  }

  private _append(markdownSource: string): void {
    const el = document.createElement("div");
    el.className = "turn";
    el.innerHTML = marked.parse(markdownSource) as string;
    this._container.appendChild(el);
    el.scrollIntoView({ block: "end" });
  }
}
