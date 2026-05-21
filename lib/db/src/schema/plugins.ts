import { pgTable, text, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const pluginsTable = pgTable("plugins", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  version: text("version").notNull().default("1.0.0"),
  description: text("description"),
  author: text("author"),
  category: text("category").notNull().default("general"),
  enabled: boolean("enabled").notNull().default(false),
  config: text("config"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertPluginSchema = createInsertSchema(pluginsTable).omit({ createdAt: true, updatedAt: true });
export type InsertPlugin = z.infer<typeof insertPluginSchema>;
export type Plugin = typeof pluginsTable.$inferSelect;
