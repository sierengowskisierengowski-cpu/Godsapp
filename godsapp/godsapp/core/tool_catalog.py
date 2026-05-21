"""Authoritative catalog of every external tool GodsApp knows about.

Each entry maps a *tool_id* (matches `Tool.requires_binary` strings used
throughout the codebase) to:

- `binaries`: every binary name we'll accept as "installed". Real example
  from a user report: pacman's `metasploit-6.4.x` ships `/usr/bin/msfconsole`
  but no `/usr/bin/metasploit`, so we have to look for both.
- `category` / `description` / `difficulty`: UI metadata
- `install`: per-package-manager install command (no `sudo` prefix; we add
  pkexec wrapping ourselves)
- `unlocks`: short list of GodsApp features the tool enables, so a user
  can decide if they actually care
- `alternatives`: related tool_ids that can substitute for this one
- `notes`: free-form gotchas (AUR-only, broken upstream, etc.)

Author: Joseph Sierengowski.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CatalogEntry:
    tool_id: str
    title: str
    binaries: tuple[str, ...]
    category: str
    description: str
    difficulty: str = "intermediate"
    install: dict[str, str] = field(default_factory=dict)
    unlocks: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    notes: Optional[str] = None
    homepage: Optional[str] = None


# Package-manager order we present to the user when their distro is
# unknown. The keys also drive the "Install all" batching.
PKG_MANAGERS = ("pacman", "apt", "dnf", "zypper", "xbps", "brew", "pipx", "pip", "go")

PKG_LABELS = {
    "pacman": "Arch / Manjaro / CachyOS",
    "apt":    "Debian / Ubuntu / Pop / Mint",
    "dnf":    "Fedora / RHEL / Rocky",
    "zypper": "openSUSE",
    "xbps":   "Void",
    "brew":   "macOS (Homebrew)",
    "pipx":   "Cross-platform (pipx)",
    "pip":    "Cross-platform (pip — last resort)",
    "go":     "Cross-platform (Go install)",
}

# Sudo-style wrapper for each manager. None = no privilege escalation
# required (pip / pipx / brew / go install user-side).
PKG_NEEDS_PRIV = {
    "pacman": True, "apt": True, "dnf": True, "zypper": True, "xbps": True,
    "brew": False, "pipx": False, "pip": False, "go": False,
}


CATALOG: dict[str, CatalogEntry] = {
    "nmap": CatalogEntry(
        "nmap", "Nmap", ("nmap",), "recon",
        "Industry-standard network port + service scanner.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm nmap",
                 "apt": "apt-get install -y nmap",
                 "dnf": "dnf install -y nmap",
                 "zypper": "zypper install -y nmap",
                 "xbps": "xbps-install -Sy nmap",
                 "brew": "brew install nmap"},
        unlocks=("Network Recon → Nmap port + service scan",),
        alternatives=("masscan",),
        homepage="https://nmap.org",
    ),
    "masscan": CatalogEntry(
        "masscan", "Masscan", ("masscan",), "network",
        "Mass IP port scanner — faster than nmap but no service detection.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm masscan",
                 "apt": "apt-get install -y masscan",
                 "dnf": "dnf install -y masscan",
                 "brew": "brew install masscan"},
        unlocks=("Network → Masscan sweep",),
        alternatives=("nmap",),
    ),
    "gobuster": CatalogEntry(
        "gobuster", "Gobuster", ("gobuster",), "web",
        "Brute-force web paths/directories using a wordlist.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm gobuster",
                 "apt": "apt-get install -y gobuster",
                 "dnf": "dnf install -y gobuster",
                 "brew": "brew install gobuster",
                 "go": "go install github.com/OJ/gobuster/v3@latest"},
        unlocks=("Web → Gobuster directory brute force",),
        alternatives=("ffuf",),
    ),
    "ffuf": CatalogEntry(
        "ffuf", "FFUF", ("ffuf",), "web",
        "Fast modern web fuzzer.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm ffuf",
                 "apt": "apt-get install -y ffuf",
                 "brew": "brew install ffuf",
                 "go": "go install github.com/ffuf/ffuf/v2@latest"},
        unlocks=("Web → FFUF fuzzer",),
        alternatives=("gobuster",),
    ),
    "nikto": CatalogEntry(
        "nikto", "Nikto", ("nikto",), "web",
        "Web server scanner for misconfigurations and dangerous files.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm nikto",
                 "apt": "apt-get install -y nikto",
                 "dnf": "dnf install -y nikto",
                 "brew": "brew install nikto"},
        unlocks=("Web → Nikto web server scanner",),
    ),
    "whatweb": CatalogEntry(
        "whatweb", "WhatWeb", ("whatweb",), "web",
        "Identify web technologies, CMS, frameworks, JS libraries.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm whatweb",
                 "apt": "apt-get install -y whatweb",
                 "brew": "brew install whatweb"},
        unlocks=("Web → WhatWeb fingerprint",),
    ),
    "sqlmap": CatalogEntry(
        "sqlmap", "SQLMap", ("sqlmap",), "web",
        "Automatic SQL injection / DB takeover.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm sqlmap",
                 "apt": "apt-get install -y sqlmap",
                 "dnf": "dnf install -y python3-sqlmap",
                 "brew": "brew install sqlmap",
                 "pipx": "pipx install sqlmap"},
        unlocks=("Web → SQLMap SQL injection",),
    ),
    "wpscan": CatalogEntry(
        "wpscan", "WPScan", ("wpscan",), "web",
        "WordPress vulnerability scanner.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm wpscan",
                 "apt": "apt-get install -y wpscan",
                 "brew": "brew install wpscanteam/tap/wpscan"},
        unlocks=("Web → WPScan WordPress audit",),
    ),
    "nuclei": CatalogEntry(
        "nuclei", "Nuclei", ("nuclei",), "vuln",
        "Fast template-based vulnerability scanner from ProjectDiscovery.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm nuclei",
                 "apt": "apt-get install -y nuclei",
                 "brew": "brew install nuclei",
                 "go": "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"},
        unlocks=("Vulnerability → Nuclei scanner",),
    ),
    "hashcat": CatalogEntry(
        "hashcat", "Hashcat", ("hashcat",), "password",
        "GPU-accelerated password hash cracker.",
        "expert",
        install={"pacman": "pacman -S --needed --noconfirm hashcat",
                 "apt": "apt-get install -y hashcat",
                 "dnf": "dnf install -y hashcat",
                 "brew": "brew install hashcat"},
        unlocks=("Password → Hashcat GPU recovery",),
        alternatives=("john",),
    ),
    "john": CatalogEntry(
        "john", "John the Ripper", ("john",), "password",
        "CPU password hash cracker (Jumbo build).",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm john",
                 "apt": "apt-get install -y john",
                 "dnf": "dnf install -y john",
                 "brew": "brew install john-jumbo"},
        unlocks=("Password → John the Ripper",),
        alternatives=("hashcat",),
    ),
    "hydra": CatalogEntry(
        "hydra", "Hydra", ("hydra",), "password",
        "Network login brute-forcer (SSH, FTP, HTTP, SMB, etc.).",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm hydra",
                 "apt": "apt-get install -y hydra",
                 "dnf": "dnf install -y hydra",
                 "brew": "brew install hydra"},
        unlocks=("Password → Hydra online brute force",),
    ),
    "yara": CatalogEntry(
        "yara", "YARA", ("yara", "yarac"), "malware",
        "Pattern-based malware identification engine.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm yara",
                 "apt": "apt-get install -y yara",
                 "dnf": "dnf install -y yara",
                 "brew": "brew install yara"},
        unlocks=("Malware → YARA rule scan",),
    ),
    "clamscan": CatalogEntry(
        "clamscan", "ClamAV", ("clamscan", "clamd"), "malware",
        "Open-source signature-based antivirus.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm clamav",
                 "apt": "apt-get install -y clamav",
                 "dnf": "dnf install -y clamav",
                 "brew": "brew install clamav"},
        unlocks=("Malware → ClamAV signature scan",),
        notes="On first install run `freshclam` to download the signature DB.",
    ),
    "theHarvester": CatalogEntry(
        "theHarvester", "theHarvester",
        ("theHarvester", "theharvester", "theharvester-git"),
        "osint",
        "Email, subdomain, and host gatherer from public sources.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm theharvester",
                 "apt": "apt-get install -y theharvester",
                 "brew": "brew install theharvester",
                 "pipx": "pipx install theHarvester",
                 "pip": "pip install theHarvester --break-system-packages"},
        unlocks=("OSINT → theHarvester gather",),
        notes=("Arch's official repo ships `theharvester`. The AUR "
               "`theharvester-git` package is sometimes broken on its "
               "`aiomultiprocess` dependency — fall back to `pipx install "
               "theHarvester` if AUR fails."),
    ),
    "whois": CatalogEntry(
        "whois", "whois", ("whois",), "osint",
        "Domain registration lookup.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm whois",
                 "apt": "apt-get install -y whois",
                 "dnf": "dnf install -y whois",
                 "brew": "brew install whois"},
        unlocks=("OSINT → whois lookup",),
    ),
    "sherlock": CatalogEntry(
        "sherlock", "Sherlock", ("sherlock", "sherlock-project"), "osint",
        "Hunt usernames across 400+ social networks.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm sherlock",
                 "apt": "apt-get install -y sherlock",
                 "brew": "brew install sherlock",
                 "pipx": "pipx install sherlock-project"},
        unlocks=("OSINT → Sherlock username hunt",),
    ),
    "searchsploit": CatalogEntry(
        "searchsploit", "SearchSploit", ("searchsploit",), "exploit",
        "Local exploit-DB index search.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm exploitdb",
                 "apt": "apt-get install -y exploitdb",
                 "dnf": "dnf install -y exploitdb",
                 "brew": "brew install exploitdb"},
        unlocks=("Exploit → SearchSploit lookup",),
    ),
    "msfvenom": CatalogEntry(
        "msfvenom", "Metasploit",
        ("msfvenom", "msfconsole", "msfd", "metasploit"),
        "exploit",
        "Metasploit Framework — payload generation, exploitation, post-ex.",
        "expert",
        install={"pacman": "pacman -S --needed --noconfirm metasploit",
                 "apt": "apt-get install -y metasploit-framework",
                 "brew": "brew install metasploit"},
        unlocks=("Exploit → msfvenom payload generator",),
        notes=("Pacman's `metasploit` package installs the binary as "
               "`/usr/bin/msfconsole`, not `/usr/bin/metasploit`. We accept "
               "any of msfvenom / msfconsole / msfd / metasploit."),
    ),
    "adb": CatalogEntry(
        "adb", "ADB", ("adb",), "mobile",
        "Android Debug Bridge.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm android-tools",
                 "apt": "apt-get install -y android-tools-adb",
                 "dnf": "dnf install -y android-tools",
                 "brew": "brew install --cask android-platform-tools"},
        unlocks=("Mobile → ADB device info",),
    ),
    "apktool": CatalogEntry(
        "apktool", "Apktool", ("apktool",), "mobile",
        "Decompile and rebuild Android APKs.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm apktool",
                 "apt": "apt-get install -y apktool",
                 "brew": "brew install apktool"},
        unlocks=("Mobile → Apktool decompile",),
    ),
    "aws": CatalogEntry(
        "aws", "AWS CLI", ("aws", "aws-cli"), "cloud",
        "Official AWS command-line interface.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm aws-cli",
                 "apt": "apt-get install -y awscli",
                 "dnf": "dnf install -y awscli",
                 "brew": "brew install awscli",
                 "pipx": "pipx install awscli"},
        unlocks=("Cloud → AWS STS caller identity",),
    ),
    "gcloud": CatalogEntry(
        "gcloud", "Google Cloud SDK", ("gcloud",), "cloud",
        "Google Cloud Platform CLI.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm google-cloud-cli",
                 "brew": "brew install --cask google-cloud-sdk"},
        unlocks=("Cloud → gcloud info",),
        notes="Debian/Ubuntu/Fedora need Google's apt/yum repo — see https://cloud.google.com/sdk/docs/install",
    ),
    "binwalk": CatalogEntry(
        "binwalk", "Binwalk", ("binwalk",), "forensics",
        "Firmware analysis tool — finds embedded files and code.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm binwalk",
                 "apt": "apt-get install -y binwalk",
                 "dnf": "dnf install -y binwalk",
                 "brew": "brew install binwalk"},
        unlocks=("Forensics → Binwalk firmware extract",),
    ),
    "exiftool": CatalogEntry(
        "exiftool", "ExifTool", ("exiftool",), "forensics",
        "Read/write EXIF metadata for images, video, documents.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm perl-image-exiftool",
                 "apt": "apt-get install -y libimage-exiftool-perl",
                 "dnf": "dnf install -y perl-Image-ExifTool",
                 "brew": "brew install exiftool"},
        unlocks=("Forensics → EXIF metadata reader",),
    ),
    "strings": CatalogEntry(
        "strings", "strings (binutils)", ("strings",), "forensics",
        "Print printable strings from binaries.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm binutils",
                 "apt": "apt-get install -y binutils",
                 "dnf": "dnf install -y binutils",
                 "brew": "brew install binutils"},
        unlocks=("Forensics → strings",),
    ),
    "openssl": CatalogEntry(
        "openssl", "OpenSSL", ("openssl",), "crypto",
        "TLS/SSL toolkit and general-purpose crypto utility.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm openssl",
                 "apt": "apt-get install -y openssl",
                 "dnf": "dnf install -y openssl",
                 "brew": "brew install openssl"},
        unlocks=("Crypto → OpenSSL hash + cipher tools",),
    ),
    "iwlist": CatalogEntry(
        "iwlist", "wireless-tools", ("iwlist",), "wireless",
        "Wi-Fi scan + interface inspection.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm wireless_tools",
                 "apt": "apt-get install -y wireless-tools",
                 "dnf": "dnf install -y wireless-tools"},
        unlocks=("Wireless → iwlist Wi-Fi scan",),
        notes="Wireless-tools is being replaced by `iw` on modern distros, but iwlist still ships on most.",
    ),
    "airodump-ng": CatalogEntry(
        "airodump-ng", "Aircrack-ng (airodump-ng)", ("airodump-ng",), "wireless",
        "802.11 frame capture from a monitor-mode interface.",
        "expert",
        install={"pacman": "pacman -S --needed --noconfirm aircrack-ng",
                 "apt": "apt-get install -y aircrack-ng",
                 "dnf": "dnf install -y aircrack-ng",
                 "brew": "brew install aircrack-ng"},
        unlocks=("Wireless → airodump-ng capture",),
    ),
    "dig": CatalogEntry(
        "dig", "dig (BIND)", ("dig",), "network",
        "DNS lookup tool.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm bind",
                 "apt": "apt-get install -y dnsutils",
                 "dnf": "dnf install -y bind-utils",
                 "brew": "brew install bind"},
        unlocks=("Network → dig DNS query",),
    ),
    "arp-scan": CatalogEntry(
        "arp-scan", "arp-scan", ("arp-scan",), "network",
        "Layer-2 ARP host discovery.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm arp-scan",
                 "apt": "apt-get install -y arp-scan",
                 "dnf": "dnf install -y arp-scan",
                 "brew": "brew install arp-scan"},
        unlocks=("Network → arp-scan LAN sweep",),
    ),
    "traceroute": CatalogEntry(
        "traceroute", "traceroute", ("traceroute",), "network",
        "Trace the network path to a host.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm traceroute",
                 "apt": "apt-get install -y traceroute",
                 "dnf": "dnf install -y traceroute"},
        unlocks=("Network → traceroute",),
    ),
    "ss": CatalogEntry(
        "ss", "ss (iproute2)", ("ss",), "network",
        "Socket statistics — listening ports, established connections.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm iproute2",
                 "apt": "apt-get install -y iproute2",
                 "dnf": "dnf install -y iproute"},
        unlocks=("Network → ss listening sockets",),
    ),
    "tshark": CatalogEntry(
        "tshark", "TShark / Wireshark CLI",
        ("tshark", "wireshark-cli"), "network",
        "Command-line packet capture + dissector.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm wireshark-cli",
                 "apt": "apt-get install -y tshark",
                 "dnf": "dnf install -y wireshark-cli",
                 "brew": "brew install --cask wireshark"},
        unlocks=("Network → packet capture",),
    ),
    "tcpdump": CatalogEntry(
        "tcpdump", "tcpdump", ("tcpdump",), "network",
        "Low-level packet capture.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm tcpdump",
                 "apt": "apt-get install -y tcpdump",
                 "dnf": "dnf install -y tcpdump",
                 "brew": "brew install tcpdump"},
        unlocks=("Network → tcpdump capture",),
    ),
    "amass": CatalogEntry(
        "amass", "OWASP Amass", ("amass",), "recon",
        "In-depth subdomain enumeration.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm amass",
                 "apt": "apt-get install -y amass",
                 "brew": "brew install amass",
                 "go": "go install -v github.com/owasp-amass/amass/v4/...@master"},
        unlocks=("Recon → Amass enumeration",),
        alternatives=("subfinder",),
    ),
    "subfinder": CatalogEntry(
        "subfinder", "subfinder", ("subfinder",), "recon",
        "Fast passive subdomain enumeration.",
        "beginner",
        install={"pacman": "pacman -S --needed --noconfirm subfinder",
                 "apt": "apt-get install -y subfinder",
                 "brew": "brew install subfinder",
                 "go": "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"},
        unlocks=("Recon → subfinder",),
        alternatives=("amass",),
    ),
    "dnsrecon": CatalogEntry(
        "dnsrecon", "DNSRecon", ("dnsrecon",), "recon",
        "DNS enumeration, brute force, and zone transfer.",
        "intermediate",
        install={"pacman": "pacman -S --needed --noconfirm dnsrecon",
                 "apt": "apt-get install -y dnsrecon",
                 "pipx": "pipx install dnsrecon"},
        unlocks=("Recon → DNSRecon",),
    ),
}


def all_ids() -> list[str]:
    return sorted(CATALOG.keys())


def get(tool_id: str) -> Optional[CatalogEntry]:
    return CATALOG.get(tool_id)


def by_category() -> dict[str, list[CatalogEntry]]:
    out: dict[str, list[CatalogEntry]] = {}
    for e in CATALOG.values():
        out.setdefault(e.category, []).append(e)
    for v in out.values():
        v.sort(key=lambda e: e.tool_id)
    return out
