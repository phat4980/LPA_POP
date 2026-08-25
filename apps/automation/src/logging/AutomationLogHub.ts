import type { LogEntry, LogLevel, LogStore } from "./LogStore.js";

type Subscriber = (entry: LogEntry) => void;

export class AutomationLogHub {
  private readonly subscribers = new Map<string, Set<Subscriber>>();

  constructor(private readonly store: LogStore) {}

  publish(automationJobId: string, level: LogLevel, message: string, ts = new Date().toISOString()): void {
    const entry: LogEntry = { automationJobId, level, message, ts };
    for (const subscriber of this.subscribers.get(automationJobId) ?? []) subscriber(entry);
    queueMicrotask(() => {
      try { this.store.append(entry); } catch (error) { console.error("Failed to persist automation log:", error); }
    });
  }

  list(automationJobId: string): LogEntry[] { return this.store.list(automationJobId); }

  subscribe(automationJobId: string, subscriber: Subscriber): () => void {
    const subscribers = this.subscribers.get(automationJobId) ?? new Set<Subscriber>();
    subscribers.add(subscriber);
    this.subscribers.set(automationJobId, subscribers);
    return () => { subscribers.delete(subscriber); if (subscribers.size === 0) this.subscribers.delete(automationJobId); };
  }
}
