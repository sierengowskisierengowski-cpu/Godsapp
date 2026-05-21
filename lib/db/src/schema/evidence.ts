import { pgTable, text, timestamp, uuid, serial } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { workspacesTable } from "./workspaces";
import { findingsTable } from "./findings";

export const evidenceTable = pgTable("evidence", {
  id: uuid("id").primaryKey().defaultRandom(),
  workspaceId: uuid("workspace_id").notNull().references(() => workspacesTable.id, { onDelete: "cascade" }),
  findingId: uuid("finding_id").references(() => findingsTable.id, { onDelete: "set null" }),
  name: text("name").notNull(),
  type: text("type").notNull().default("text"),
  description: text("description"),
  content: text("content"),
  hash: text("hash"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const custodyChainTable = pgTable("custody_chain", {
  id: serial("id").primaryKey(),
  evidenceId: uuid("evidence_id").notNull().references(() => evidenceTable.id, { onDelete: "cascade" }),
  actor: text("actor").notNull().default("operator"),
  action: text("action").notNull(),
  notes: text("notes"),
  timestamp: timestamp("timestamp", { withTimezone: true }).notNull().defaultNow(),
});

export const insertEvidenceSchema = createInsertSchema(evidenceTable).omit({ id: true, createdAt: true, updatedAt: true });
export type InsertEvidence = z.infer<typeof insertEvidenceSchema>;
export type Evidence = typeof evidenceTable.$inferSelect;
export type CustodyEntry = typeof custodyChainTable.$inferSelect;
