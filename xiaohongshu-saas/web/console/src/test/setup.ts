import "@testing-library/jest-dom/vitest";

// EventSource is not implemented in jsdom. Pages that opt into SSE only run
// under vitest with this no-op shim; the hook still surfaces an error in
// `error` rather than throwing synchronously.
if (typeof globalThis.EventSource === "undefined") {
  class FakeEventSource {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSED = 2;
    url: string;
    readyState = 0;
    onopen: ((ev: Event) => void) | null = null;
    onmessage: ((ev: MessageEvent) => void) | null = null;
    onerror: ((ev: Event) => void) | null = null;
    constructor(url: string) {
      this.url = url;
      // never emits — keeps React tree mountable; tests don't assert on SSE events
    }
    close() {
      this.readyState = 2;
    }
    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() {
      return true;
    }
  }
  (globalThis as { EventSource?: typeof EventSource }).EventSource =
    FakeEventSource as unknown as typeof EventSource;
}
