// clients/vscode/extension-host/src/inline_strip_manager.test.ts
import assert from "node:assert/strict";
import { InlineStripManager, type StripDecorator } from "./inline_strip_manager";

class FakeDecorator implements StripDecorator {
  calls: Array<{ op: "set"; line: number; text: string } | { op: "clear" }> = [];

  setDecoration(line: number, text: string): void {
    this.calls.push({ op: "set", line, text });
  }

  clearDecoration(): void {
    this.calls.push({ op: "clear" });
  }
}

function makeManager() {
  const decorator = new FakeDecorator();
  const contextCalls: Array<{ key: string; value: boolean }> = [];
  const manager = new InlineStripManager(decorator, (key, value) => {
    contextCalls.push({ key, value });
  });
  return { manager, decorator, contextCalls };
}

describe("InlineStripManager", () => {
  it("is not visible before show() is called", () => {
    const { manager } = makeManager();
    assert.equal(manager.isVisible, false);
    assert.equal(manager.visibleLine, null);
  });

  it("show() sets the context key, marks visible, and renders the initial status", () => {
    const { manager, decorator, contextCalls } = makeManager();
    manager.show(5);
    assert.equal(manager.isVisible, true);
    assert.equal(manager.visibleLine, 5);
    assert.deepEqual(contextCalls, [{ key: "breakdown.stripVisible", value: true }]);
    assert.deepEqual(decorator.calls, [{ op: "set", line: 5, text: "explaining…" }]);
  });

  it("moveTo() replaces the decoration at the new line instead of stacking", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.moveTo(10);
    assert.equal(manager.visibleLine, 10);
    assert.deepEqual(decorator.calls, [
      { op: "set", line: 5, text: "explaining…" },
      { op: "set", line: 10, text: "explaining…" },
    ]);
  });

  it("moveTo() is a no-op when the strip is not visible", () => {
    const { manager, decorator } = makeManager();
    manager.moveTo(10);
    assert.equal(manager.isVisible, false);
    assert.deepEqual(decorator.calls, []);
  });

  it("updateStatus() re-renders with the new status while visible", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.updateStatus("idle");
    assert.deepEqual(decorator.calls[1], { op: "set", line: 5, text: "idle…" });
  });

  it("updateStatus() is a no-op when the strip is not visible", () => {
    const { manager, decorator } = makeManager();
    manager.updateStatus("idle");
    assert.deepEqual(decorator.calls, []);
  });

  it("dismiss() clears the decoration, resets the context key, and hides the strip", () => {
    const { manager, decorator, contextCalls } = makeManager();
    manager.show(5);
    manager.dismiss();
    assert.equal(manager.isVisible, false);
    assert.equal(manager.visibleLine, null);
    assert.deepEqual(contextCalls, [
      { key: "breakdown.stripVisible", value: true },
      { key: "breakdown.stripVisible", value: false },
    ]);
    assert.deepEqual(decorator.calls[1], { op: "clear" });
  });

  it("show() on a second line after dismiss() starts a fresh render", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.dismiss();
    manager.show(7);
    assert.deepEqual(decorator.calls[2], { op: "set", line: 7, text: "explaining…" });
  });
});
