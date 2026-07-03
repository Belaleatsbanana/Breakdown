// clients/vscode/extension-host/src/inline_strip_manager.ts
// Mirrors the status.state literal union in ./message_types.ts, kept as a
// manual copy in the same style that file already uses for the webview types.
export type StripStatus = "idle" | "explaining" | "listening" | "interrupted";

export interface StripDecorator {
  setDecoration(line: number, text: string): void;
  clearDecoration(): void;
}

export type ContextSetter = (key: string, value: boolean) => void;

const CONTEXT_KEY = "breakdown.stripVisible";

export class InlineStripManager {
  private _visibleLine: number | null = null;
  private _status: StripStatus = "explaining";

  constructor(
    private readonly _decorator: StripDecorator,
    private readonly _setContext: ContextSetter,
  ) {}

  get isVisible(): boolean {
    return this._visibleLine !== null;
  }

  get visibleLine(): number | null {
    return this._visibleLine;
  }

  show(line: number): void {
    this._visibleLine = line;
    this._status = "explaining";
    this._setContext(CONTEXT_KEY, true);
    this._render();
  }

  moveTo(line: number): void {
    if (this._visibleLine === null) {
      return;
    }
    this._visibleLine = line;
    this._render();
  }

  updateStatus(status: StripStatus): void {
    if (this._visibleLine === null) {
      return;
    }
    this._status = status;
    this._render();
  }

  dismiss(): void {
    this._visibleLine = null;
    this._status = "explaining";
    this._setContext(CONTEXT_KEY, false);
    this._decorator.clearDecoration();
  }

  private _render(): void {
    if (this._visibleLine === null) {
      return;
    }
    this._decorator.setDecoration(this._visibleLine, `${this._status}…`);
  }
}
