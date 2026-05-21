import { Router } from "express";
import { db } from "@workspace/db";
import { evidenceTable, custodyChainTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";
import crypto from "crypto";

const router = Router();

router.get("/workspaces/:workspaceId/evidence", requireAuth, async (req, res) => {
  const items = await db.select().from(evidenceTable).where(eq(evidenceTable.workspaceId, req.params.workspaceId)).orderBy(evidenceTable.createdAt);
  res.json(items);
});

router.post("/workspaces/:workspaceId/evidence", requireAuth, async (req, res) => {
  const { name, type, description, content, findingId } = req.body;
  if (!name) { res.status(400).json({ error: "Name required" }); return; }
  const hash = content ? crypto.createHash("sha256").update(content).digest("hex") : null;
  const [item] = await db.insert(evidenceTable).values({ workspaceId: req.params.workspaceId, findingId: findingId ?? null, name, type: type ?? "text", description, content, hash }).returning();
  await db.insert(custodyChainTable).values({ evidenceId: item.id, actor: "operator", action: "created", notes: "Evidence created" });
  await logAudit("evidence.created", { resource: "evidence", resourceId: item.id, req });
  res.status(201).json(item);
});

router.get("/workspaces/:workspaceId/evidence/:evidenceId", requireAuth, async (req, res) => {
  const [item] = await db.select().from(evidenceTable).where(and(eq(evidenceTable.id, req.params.evidenceId), eq(evidenceTable.workspaceId, req.params.workspaceId))).limit(1);
  if (!item) { res.status(404).json({ error: "Evidence not found" }); return; }
  await db.insert(custodyChainTable).values({ evidenceId: item.id, actor: "operator", action: "viewed" });
  res.json(item);
});

router.delete("/workspaces/:workspaceId/evidence/:evidenceId", requireAuth, async (req, res) => {
  const [item] = await db.delete(evidenceTable).where(and(eq(evidenceTable.id, req.params.evidenceId), eq(evidenceTable.workspaceId, req.params.workspaceId))).returning();
  if (!item) { res.status(404).json({ error: "Evidence not found" }); return; }
  await logAudit("evidence.deleted", { resource: "evidence", resourceId: req.params.evidenceId, req });
  res.json({ success: true });
});

router.get("/workspaces/:workspaceId/evidence/:evidenceId/custody", requireAuth, async (req, res) => {
  const entries = await db.select().from(custodyChainTable).where(eq(custodyChainTable.evidenceId, req.params.evidenceId)).orderBy(custodyChainTable.timestamp);
  res.json(entries);
});

export default router;
