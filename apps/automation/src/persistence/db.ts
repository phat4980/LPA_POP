import { mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

export type SqliteStatement = {
  run(...params: unknown[]): void;
  all(...params: unknown[]): unknown[];
  get(...params: unknown[]): unknown;
};

export type SqliteDatabase = {
  exec(sql: string): void;
  prepare(sql: string): SqliteStatement;
  close(): void;
};

export function openDatabase(databasePath: string): SqliteDatabase {
  const DatabaseSync = (createRequire(import.meta.url)("node:sqlite") as {
    DatabaseSync: new (path: string) => SqliteDatabase;
  }).DatabaseSync;
  const path = resolve(databasePath);
  mkdirSync(dirname(path), { recursive: true });
  const database = new DatabaseSync(path);
  applyMigrations(database);
  return database;
}

function applyMigrations(database: SqliteDatabase): void {
  database.exec("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)");
  const migrations = [
    [1, "logs", "001_logs.sql"],
    [2, "jobs", "002_jobs.sql"],
  ] as const;
  for (const [version, name, fileName] of migrations) {
    const applied = database.prepare("SELECT version FROM schema_migrations WHERE version = ?").get(version);
    if (applied) continue;
    if (version === 1 && tableExists(database, "logs")) {
      database.prepare("INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)").run(version, name, new Date().toISOString());
      continue;
    }
    const path = fileURLToPath(new URL(`./migrations/${fileName}`, import.meta.url));
    database.exec(readFileSync(path, "utf8"));
    database.prepare("INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)").run(version, name, new Date().toISOString());
  }
}

function tableExists(database: SqliteDatabase, tableName: string): boolean {
  return Boolean(database.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?").get(tableName));
}
