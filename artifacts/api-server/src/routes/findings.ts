import { Router } from "express";
import { db } from "@workspace/db";
import { findingsTable } from "@workspace/db";
import { eq, and, count } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

router.get("/workspaces/:workspaceId/findings", requireAuth, async (req, res) => {
  const findings = await db.select().from(findingsTable).where(eq(findingsTable.workspaceId, req.params.workspaceId)).orderBy(findingsTable.createdAt);
  res.json(findings);
});

router.post("/workspaces/:workspaceId/findings", requireAuth, async (req, res) => {
  const { title, description, severity, status, cvss, cve, evidence, recommendation, affectedComponent, refs, scanId } = req.body;
  if (!title) { res.status(400).json({ error: "Title required" }); return; }
  const [finding] = await db.insert(findingsTable).values({ workspaceId: req.params.workspaceId, scanId: scanId ?? null, title, description, severity: severity ?? "info", status: status ?? "open", cvss, cve, evidence, recommendation, affectedComponent, refs }).returning();
  await logAudit("finding.created", { resource: "finding", resourceId: finding.id, req });
  res.status(201).json(finding);
});

router.get("/workspaces/:workspaceId/findings/summary", requireAuth, async (req, res) => {
  const rows = await db.select({ severity: findingsTable.severity, count: count() }).from(findingsTable).where(eq(findingsTable.workspaceId, req.params.workspaceId)).groupBy(findingsTable.severity);
  const summary: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const row of rows) summary[row.severity] = Number(row.count);
  res.json(summary);
});

router.get("/workspaces/:workspaceId/findings/:findingId", requireAuth, async (req, res) => {
  const [finding] = await db.select().from(findingsTable).where(and(eq(findingsTable.id, req.params.findingId), eq(findingsTable.workspaceId, req.params.workspaceId))).limit(1);
  if (!finding) { res.status(404).json({ error: "Finding not found" }); return; }
  res.json(finding);
});

router.put("/workspaces/:workspaceId/findings/:findingId", requireAuth, async (req, res) => {
  const { title, description, severity, status, cvss, cve, evidence, recommendation, affectedComponent, refs } = req.body;
  const [finding] = await db.update(findingsTable).set({ title, description, severity, status, cvss, cve, evidence, recommendation, affectedComponent, refs }).where(and(eq(findingsTable.id, req.params.findingId), eq(findingsTable.workspaceId, req.params.workspaceId))).returning();
  if (!finding) { res.status(404).json({ error: "Finding not found" }); return; }
  await logAudit("finding.updated", { resource: "finding", resourceId: finding.id, req });
  res.json(finding);
});

router.delete("/workspaces/:workspaceId/findings/:findingId", requireAuth, async (req, res) => {
  const [finding] = await db.delete(findingsTable).where(and(eq(findingsTable.id, req.params.findingId), eq(findingsTable.workspaceId, req.params.workspaceId))).returning();
  if (!finding) { res.status(404).json({ error: "Finding not found" }); return; }
  await logAudit("finding.deleted", { resource: "finding", resourceId: req.params.findingId, req });
  res.json({ success: true });
});

export default router;
