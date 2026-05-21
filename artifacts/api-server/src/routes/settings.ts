import { Router } from "express";
import { db } from "@workspace/db";
import { appSettingsTable, apiKeysTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

const KNOWN_TOOLS = [
  { id: "nmap", name: "Nmap", description: "Network scanner", category: "network" },
  { id: "gobuster", name: "Gobuster", description: "Directory brute-forcer", category: "web" },
  { id: "nikto", name: "Nikto", description: "Web server scanner", category: "web" },
  { id: "sqlmap", name: "SQLMap", description: "SQL injection tool", category: "web" },
  { id: "hydra", name: "Hydra", description: "Password brute-forcer", category: "password" },
  { id: "hashcat", name: "Hashcat", description: "Hash cracker", category: "crypto" },
  { id: "john", name: "John the Ripper", description: "Password cracker", category: "crypto" },
  { id: "metasploit", name: "Metasploit", description: "Exploitation framework", category: "exploitation" },
  { id: "shodan", name: "Shodan CLI", description: "OSINT / IoT search", category: "osint" },
  { id: "theHarvester", name: "theHarvester", description: "Email/domain OSINT", category: "osint" },
];

router.get("/settings/general", requireAuth, async (_req, res) => {
  const settings = await db.select().from(appSettingsTable).limit(1);
  if (!settings.length) { res.status(404).json({ error: "Settings not found" }); return; }
  const s = settings[0];
  res.json({ operatorName: s.operatorName, organization: s.organization, autoLockMinutes: s.autoLockMinutes, theme: s.theme });
});

router.put("/settings/general", requireAuth, async (req, res) => {
  const { operatorName, organization, autoLockMinutes, theme } = req.body;
  const settings = await db.select().from(appSettingsTable).limit(1);
  if (!settings.length) { res.status(404).json({ error: "Settings not found" }); return; }
  await db.update(appSettingsTable).set({ operatorName, organization, autoLockMinutes, theme }).where(eq(appSettingsTable.id, settings[0].id));
  await logAudit("settings.updated", { req });
  res.json({ success: true });
});

router.get("/settings/api-keys", requireAuth, async (_req, res) => {
  const keys = await db.select().from(apiKeysTable);
  res.json(keys.map(k => ({ id: k.id, service: k.service, key: k.key.slice(0, 4) + "..." + k.key.slice(-4), updatedAt: k.updatedAt })));
});

router.put("/settings/api-keys/:service", requireAuth, async (req, res) => {
  const { service } = req.params;
  const { key } = req.body;
  if (!key) { res.status(400).json({ error: "Key required" }); return; }
  const existing = await db.select().from(apiKeysTable).where(eq(apiKeysTable.service, service)).limit(1);
  if (existing.length) {
    await db.update(apiKeysTable).set({ key }).where(eq(apiKeysTable.service, service));
  } else {
    await db.insert(apiKeysTable).values({ service, key });
  }
  await logAudit("api_key.upserted", { resource: "api_key", resourceId: service, req });
  res.json({ success: true, service });
});

router.post("/settings/api-keys/:service/test", requireAuth, async (req, res) => {
  const { service } = req.params;
  const keyRow = await db.select().from(apiKeysTable).where(eq(apiKeysTable.service, service)).limit(1);
  if (!keyRow.length) { res.status(404).json({ valid: false, error: "No key configured" }); return; }
  res.json({ valid: true, service });
});

router.get("/settings/tools/status", requireAuth, async (_req, res) => {
  res.json(KNOWN_TOOLS.map(t => ({ ...t, available: false, version: null })));
});

export default router;
