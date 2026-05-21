import { Router } from "express";
import { db } from "@workspace/db";
import { pluginsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

const BUILTIN_PLUGINS = [
  { id: "nmap-scanner", name: "Nmap Scanner", version: "1.0.0", description: "Network discovery and security auditing", author: "Gordon Lyon", category: "network" },
  { id: "gobuster", name: "Gobuster", version: "3.6.0", description: "Directory/file & DNS busting tool", author: "OJ Reeves", category: "web" },
  { id: "nikto", name: "Nikto", version: "2.1.6", description: "Web server vulnerability scanner", author: "Chris Sullo", category: "web" },
  { id: "sqlmap", name: "SQLMap", version: "1.7.0", description: "Automatic SQL injection and database takeover", author: "SQLMap Team", category: "web" },
  { id: "hydra", name: "Hydra", version: "9.4", description: "Fast and flexible online password cracker", author: "van Hauser", category: "password" },
  { id: "hashcat", name: "Hashcat", version: "6.2.6", description: "World's fastest password cracker", author: "Jens Steube", category: "crypto" },
  { id: "john", name: "John the Ripper", version: "1.9.0", description: "Open source password security auditing", author: "Openwall", category: "crypto" },
  { id: "volatility3", name: "Volatility 3", version: "2.4.1", description: "Memory forensics framework", author: "Volatility Foundation", category: "forensics" },
  { id: "theHarvester", name: "theHarvester", version: "4.4.0", description: "OSINT information gathering tool", author: "Christian Martorella", category: "osint" },
  { id: "shodan-cli", name: "Shodan CLI", version: "1.9.1", description: "Command-line interface for Shodan", author: "Shodan", category: "osint" },
  { id: "metasploit", name: "Metasploit Framework", version: "6.3.0", description: "Penetration testing framework", author: "Rapid7", category: "exploitation" },
  { id: "wireshark-tshark", name: "Wireshark (tshark)", version: "4.0.0", description: "Network protocol analyzer", author: "Wireshark Foundation", category: "forensics" },
];

async function seedPlugins() {
  const existing = await db.select({ id: pluginsTable.id }).from(pluginsTable);
  const existingIds = new Set(existing.map(p => p.id));
  for (const p of BUILTIN_PLUGINS) {
    if (!existingIds.has(p.id)) {
      await db.insert(pluginsTable).values({ ...p, enabled: false }).catch(() => {});
    }
  }
}

router.get("/plugins", requireAuth, async (_req, res) => {
  await seedPlugins();
  const plugins = await db.select().from(pluginsTable).orderBy(pluginsTable.category);
  res.json(plugins);
});

router.post("/plugins/:id/toggle", requireAuth, async (req, res) => {
  const [plugin] = await db.select().from(pluginsTable).where(eq(pluginsTable.id, req.params.id)).limit(1);
  if (!plugin) { res.status(404).json({ error: "Plugin not found" }); return; }
  const [updated] = await db.update(pluginsTable).set({ enabled: !plugin.enabled }).where(eq(pluginsTable.id, req.params.id)).returning();
  await logAudit(`plugin.${updated.enabled ? "enabled" : "disabled"}`, { resource: "plugin", resourceId: req.params.id, req });
  res.json(updated);
});

export default router;
