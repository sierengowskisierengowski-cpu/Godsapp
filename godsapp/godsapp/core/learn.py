"""Learn Mode content — per-tool inline tutorials.

Each entry follows a structured format so the UI can render it consistently.
Built-in content ships with v0.4.0 for 6 common tools; additional tools
fall back to a "no Learn content yet" placeholder that points to the
docs link in `references` or the tool's own --help.

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DIFFICULTY_BEGINNER = "beginner"
DIFFICULTY_INTERMEDIATE = "intermediate"
DIFFICULTY_EXPERT = "expert"

DIFFICULTY_LABELS = {
    DIFFICULTY_BEGINNER:     ("●", "Beginner — safe defaults, easy to use."),
    DIFFICULTY_INTERMEDIATE: ("●", "Intermediate — requires some context."),
    DIFFICULTY_EXPERT:       ("●", "Expert — destructive potential, authorisation required."),
}


@dataclass(frozen=True)
class LearnEntry:
    tool_id: str
    difficulty: str = DIFFICULTY_INTERMEDIATE
    summary: str = ""
    when_to_use: str = ""
    how_to_use: str = ""
    options_explained: tuple[tuple[str, str], ...] = ()
    examples: tuple[str, ...] = ()
    pitfalls: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    references: tuple[tuple[str, str], ...] = ()


LEARN_CONTENT: dict[str, LearnEntry] = {
    "nmap": LearnEntry(
        tool_id="nmap",
        difficulty=DIFFICULTY_BEGINNER,
        summary="Nmap is the de-facto network discovery and port-scanning tool.",
        when_to_use=(
            "Use Nmap when you need to enumerate hosts, open ports, services, and "
            "OS fingerprints on a target network you are authorised to scan."
        ),
        how_to_use=(
            "1. Provide a target (single IP, CIDR, hostname, or list).\n"
            "2. Pick a port range (top 1000 is a sensible default).\n"
            "3. Enable service/version detection if you need banners.\n"
            "4. Run. Promote interesting hosts/ports to findings."
        ),
        options_explained=(
            ("Ports",        "Range or comma list. -p- = all 65k. Default top 1000."),
            ("Timing",       "T0–T5. T3 is default, T4 faster on stable networks."),
            ("Service detect", "-sV — probes service banners. Adds time."),
            ("OS detect",    "-O — needs root and at least one open + one closed port."),
        ),
        examples=(
            "nmap -sV -p- 10.0.0.0/24",
            "nmap -sS -T4 --top-ports 1000 example.com",
            "nmap -sU -p 53,123,161 10.0.0.1",
        ),
        pitfalls=(
            "Aggressive timing (-T5) can crash fragile services.",
            "Scanning targets you do not own or have explicit authorisation for is illegal.",
            "UDP scans are slow and lossy — narrow the port list.",
        ),
        related=("masscan", "subdomain-brute", "amass"),
        references=(
            ("Nmap reference guide", "https://nmap.org/book/man.html"),
            ("MITRE T1046 — Network Service Scanning",
             "https://attack.mitre.org/techniques/T1046/"),
        ),
    ),
    "sqlmap": LearnEntry(
        tool_id="sqlmap",
        difficulty=DIFFICULTY_INTERMEDIATE,
        summary="Automated SQL injection discovery and exploitation across many DB engines.",
        when_to_use=(
            "Use after you have identified a candidate parameter that may be "
            "vulnerable to SQL injection (login forms, search boxes, IDs in URLs)."
        ),
        how_to_use=(
            "1. Capture a request (Burp/ZAP/manual) including cookies & headers.\n"
            "2. Save it to a file or paste the URL.\n"
            "3. Pick a level/risk — start low.\n"
            "4. Let sqlmap test. If injectable, enumerate DBs/tables/data."
        ),
        options_explained=(
            ("--level",  "1–5. Number of tests per parameter. Start at 1."),
            ("--risk",   "1–3. Risk of payloads. >1 may damage data."),
            ("--batch",  "Non-interactive. Use sensible defaults."),
            ("--dbs",    "Enumerate databases once injection confirmed."),
        ),
        examples=(
            "sqlmap -u 'https://x/q?id=1' --batch --level=1 --risk=1",
            "sqlmap -r request.raw --batch --dbs",
        ),
        pitfalls=(
            "--risk=3 includes UPDATE/DELETE-based payloads — can corrupt data.",
            "Always confirm authorisation; SQLi against unowned systems is illegal.",
            "Rate-limit if the target is production — sqlmap is noisy.",
        ),
        related=("nuclei", "nikto"),
        references=(
            ("sqlmap user manual", "https://github.com/sqlmapproject/sqlmap/wiki/Usage"),
            ("OWASP SQL Injection",
             "https://owasp.org/www-community/attacks/SQL_Injection"),
        ),
    ),
    "hydra": LearnEntry(
        tool_id="hydra",
        difficulty=DIFFICULTY_EXPERT,
        summary="Parallelised network logon cracker supporting SSH, FTP, HTTP-form, RDP, SMB, etc.",
        when_to_use=(
            "Use only for authorised password-strength testing on services where "
            "online brute force is in scope (e.g. credential-stuffing assessments)."
        ),
        how_to_use=(
            "1. Choose a service module (ssh, ftp, http-post-form, smb, ...).\n"
            "2. Provide username list (-L) and password list (-P).\n"
            "3. Tune parallel tasks (-t) — 16 is sane; high values lock accounts.\n"
            "4. Add -f to stop on first success."
        ),
        options_explained=(
            ("-L / -l",  "User list / single user."),
            ("-P / -p",  "Password list / single password."),
            ("-t",       "Parallel tasks. Default 16."),
            ("-f",       "Stop on first valid pair."),
            ("-V",       "Verbose — print every attempt."),
        ),
        examples=(
            "hydra -L users.txt -P rockyou.txt -t 4 ssh://10.0.0.5",
            "hydra -l admin -P passwords.txt smb://10.0.0.20",
        ),
        pitfalls=(
            "Online brute force locks out accounts. Coordinate with the client.",
            "Many services have rate limits or fail2ban — high -t will trigger them.",
            "Unauthorised use is a criminal offence in most jurisdictions.",
        ),
        related=("hashcat", "john"),
        references=(
            ("THC-Hydra docs", "https://github.com/vanhauser-thc/thc-hydra"),
            ("MITRE T1110 — Brute Force",
             "https://attack.mitre.org/techniques/T1110/"),
        ),
    ),
    "subdomain-brute": LearnEntry(
        tool_id="subdomain-brute",
        difficulty=DIFFICULTY_BEGINNER,
        summary="DNS-based enumeration of subdomains for a given apex domain.",
        when_to_use=(
            "Use during reconnaissance to expand a target's attack surface — bug "
            "bounty scopes are typically wildcards, so subdomain enumeration is step 1."
        ),
        how_to_use=(
            "1. Provide the apex domain (e.g. example.com).\n"
            "2. Pick a wordlist size (built-in small/medium/large).\n"
            "3. Run. Live hits show up in real time."
        ),
        options_explained=(
            ("Wordlist", "Larger = more coverage, more requests, more time."),
            ("Resolver", "DNS server. Use 1.1.1.1 / 8.8.8.8 or your own."),
        ),
        examples=("subdomain-brute example.com (medium wordlist)",),
        pitfalls=(
            "Very large wordlists may rate-limit you on public resolvers.",
            "Wildcards (*.example.com → all resolve) cause false positives — verify with HTTP.",
        ),
        related=("amass", "subfinder"),
        references=(
            ("OWASP Subdomain Takeover",
             "https://owasp.org/www-community/attacks/Subdomain_Takeover"),
        ),
    ),
    "hashcat": LearnEntry(
        tool_id="hashcat",
        difficulty=DIFFICULTY_EXPERT,
        summary="GPU-accelerated password hash cracker. Supports hundreds of hash types.",
        when_to_use=(
            "Use offline against hash dumps you have obtained legitimately — "
            "/etc/shadow, NTDS.dit, leaked databases under explicit authorisation."
        ),
        how_to_use=(
            "1. Identify the hash mode (-m). hashcat --example-hashes helps.\n"
            "2. Pick an attack mode (-a 0 wordlist, -a 3 mask, -a 6/-a 7 hybrid).\n"
            "3. Provide hash file + wordlist (or mask).\n"
            "4. Cracked hashes append to hashcat.potfile."
        ),
        options_explained=(
            ("-m",   "Hash mode (e.g. 1000 = NTLM, 1800 = sha512crypt)."),
            ("-a",   "Attack mode (0=wordlist, 1=combinator, 3=mask, 6/7=hybrid)."),
            ("-w",   "Workload profile (1=low, 4=insane)."),
        ),
        examples=(
            "hashcat -m 1000 -a 0 ntlm.txt rockyou.txt",
            "hashcat -m 1800 -a 3 hashes.txt '?u?l?l?l?l?d?d'",
        ),
        pitfalls=(
            "Cracking hashes you do not have authority over may be illegal.",
            "GPU drivers matter — install proprietary NVIDIA / ROCm for best speed.",
            "High -w on a laptop = thermal throttling.",
        ),
        related=("john", "hydra"),
        references=(
            ("hashcat wiki", "https://hashcat.net/wiki/"),
        ),
    ),
    "gobuster": LearnEntry(
        tool_id="gobuster",
        difficulty=DIFFICULTY_BEGINNER,
        summary="Fast HTTP path / virtual host / DNS brute-forcer.",
        when_to_use=(
            "Use to discover hidden directories, files, vhosts, or DNS records "
            "during web reconnaissance."
        ),
        how_to_use=(
            "1. Pick a mode: dir | vhost | dns.\n"
            "2. Provide URL or domain.\n"
            "3. Choose a wordlist.\n"
            "4. Filter status codes (-s) to reduce noise."
        ),
        options_explained=(
            ("-u",  "Target URL or base domain."),
            ("-w",  "Wordlist path."),
            ("-x",  "Extensions to append (php,html,bak,...)."),
            ("-t",  "Threads. Default 10."),
        ),
        examples=(
            "gobuster dir -u https://x -w common.txt -x php,html",
            "gobuster vhost -u https://x -w subdomains.txt",
        ),
        pitfalls=(
            "Threads >100 will be rate-limited or blocked.",
            "Some WAFs flag every 404 as a hit — verify with content size.",
        ),
        related=("subdomain-brute", "ffuf"),
        references=(
            ("Gobuster README", "https://github.com/OJ/gobuster"),
        ),
    ),
}


def get_learn_for_tool(tool_id: str) -> LearnEntry | None:
    return LEARN_CONTENT.get(tool_id)


def difficulty_for_tool(tool_id: str) -> str:
    entry = LEARN_CONTENT.get(tool_id)
    if entry is not None:
        return entry.difficulty
    return DIFFICULTY_INTERMEDIATE
