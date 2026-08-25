import type { LogEntry, LogLevel, LogStore } from "./LogStore.js";

type Subscriber = (entry: LogEntry) => void;

export class AutomationLogHub {
  private readonly subscribers = new Map<string, Set<Subscriber>>();
  private readonly recent = new Map<string, LogEntry[]>();

  constructor(private readonly store: LogStore) {}

  publish(automationJobId: string, level: LogLevel, message: string, ts = new Date().toISOString()): void {
    const entry: LogEntry = { automationJobId, level, message, ts };
    const entries = this.recent.get(automationJobId) ?? [];
    entries.push(entry);
    if (entries.length > 5000) entries.shift();
    this.recent.set(automationJobId, entries);
    for (const subscriber of this.subscribers.get(automationJobId) ?? []) {
      try { subscriber(entry); } catch (error) { console.error("Failed to publish automation log:", error); }
    }
    queueMicrotask(() => {
      try {
        this.store.append(entry);
        const current = this.recent.get(automationJobId);
        if (current) {
          const index = current.indexOf(entry);
          if (index >= 0) current.splice(index, 1);
          if (current.length === 0) this.recent.delete(automationJobId);
        }
      } catch (error) { console.error("Failed to persist automation log:", error); }
    });
  }

  list(automationJobId: string): LogEntry[] {
    const persisted = this.store.list(automationJobId);
    const persistedKeys = new Set(persisted.map((entry) => `${entry.ts}\u0000${entry.level}\u0000${entry.message}`));
    const pending = (this.recent.get(automationJobId) ?? []).filter((entry) => !persistedKeys.has(`${entry.ts}\u0000${entry.level}\u0000${entry.message}`));
    return [...persisted, ...pending];
  }

  subscribe(automationJobId: string, subscriber: Subscriber): () => void {
    const subscribers = this.subscribers.get(automationJobId) ?? new Set<Subscriber>();
    subscribers.add(subscriber);
    this.subscribers.set(automationJobId, subscribers);
    return () => { subscribers.delete(subscriber); if (subscribers.size === 0) this.subscribers.delete(automationJobId); };
  }
}
