# url-doctor
# 🔍 URL / API Error Diagnostic Tool

An interactive terminal tool for diagnosing HTTP errors, SSL/TLS certificate issues, DNS failures, CORS problems, and security header gaps — for any public URL, private endpoint, or API.

---

## Requirements

| Requirement | Minimum |
|-------------|---------|
| Python | 3.7 or newer |
| pip | any recent version |
| OS | Ubuntu 20.04+ (also works on macOS / Windows) |
| Network | Any — works on public URLs, private/VPN endpoints, and localhost |

The script auto-installs all missing Python packages on first run. No manual `pip install` needed.

---

## Quick Start

```bash
python3 url_diagnostics.py
```

That's it. On first run it will:

1. Detect your Python environment (venv, conda, system Python, etc.)
2. Run a pre-flight check of system tools
3. Install any missing packages safely
4. Launch the interactive diagnostic session

---

## Installation (recommended — inside a venv)

Using a virtual environment keeps your laptop's existing Python setup completely untouched.

```bash
# Create a venv (one time only)
python3 -m venv ~/.venvs/urldiag

# Activate it
source ~/.venvs/urldiag/bin/activate

# Run the tool
python3 url_diagnostics.py
```

To deactivate the venv when you're done:

```bash
deactivate
```

> **Why a venv?** The tool detects if you're running inside a system-managed Python (Ubuntu 23.04+) and will refuse to auto-install there to protect your OS. A venv sidesteps this entirely and is the cleanest option.

---

## What It Checks

The tool runs 7 diagnostic layers in sequence for every URL you test.

### 1 · DNS Resolution
Resolves the domain to IP addresses using `dnspython`. Catches `NXDOMAIN` (domain doesn't exist), DNS timeouts, and missing A-records.

### 2 · TCP Connectivity
Opens a raw TCP socket to the host and port. Measures connection latency in milliseconds. Catches connection refused, firewall blocks, and port mismatches.

### 3 · SSL / TLS Certificate
Performs a full TLS handshake and inspects the certificate. Reports:
- Certificate validity and issuer
- **Expiry date with countdown** (critical warnings at <14 days, <30 days, <60 days)
- Self-signed certificate detection
- Protocol version (warns on TLS 1.0 / 1.1)
- Subject Alternative Names (SANs)

### 4 · HTTP Response
Makes the actual HTTP request and analyses the response:
- Status code with plain-English explanation and suggested fix (covers all standard codes: 1xx–5xx plus Cloudflare-specific 521/522/524)
- Response latency with performance rating
- Full redirect chain display
- Error body snippet (pretty-printed JSON if applicable)
- Auth hints for 401 responses (`WWW-Authenticate` header)
- `Retry-After` hint for 429 rate-limit responses

### 5 · CORS Analysis
Inspects `Access-Control-*` response headers. Detects missing CORS headers, wildcard+credentials conflicts, and restricted-origin policies.

### 6 · Security Headers
Checks for 6 recommended security headers and tells you exactly what to add if any are missing:
- `Strict-Transport-Security`
- `X-Content-Type-Options`
- `X-Frame-Options`
- `Content-Security-Policy`
- `Referrer-Policy`
- `Permissions-Policy`

### 7 · Server Metadata
Displays useful response headers: `Server`, `X-Powered-By`, `Cache-Control`, `CF-Ray`, rate-limit headers, and request IDs.

---

## Interactive Session Walkthrough

When you run the tool, it walks you through a short setup before each test:

```
🌐 Enter URL or API endpoint:
```
Enter any URL. You can omit `https://` — the tool adds it automatically.

```
📡 HTTP Method:
  [1] GET
  [2] POST
  [3] PUT
  [4] PATCH
  [5] DELETE
  [6] HEAD
  [7] OPTIONS
```
Pick the method that matches your test. Default is GET.

```
Add custom headers? (y/N):
```
Type `y` to add headers one at a time in `Header-Name: value` format. Useful for:
- `Authorization: Bearer <your-token>`
- `X-API-Key: <your-key>`
- `Accept: application/json`

```
Add request body/payload? (y/N):
```
For POST/PUT/PATCH — paste JSON or plain text, then type `END` on its own line to finish.

```
⏱ Request timeout in seconds [10]:
```
Default is 10 seconds. Increase for slow APIs or large responses.

```
🔒 Verify SSL certificate? (Y/n):
```
Default is yes. Type `n` to skip SSL verification — useful for self-signed certificates on private/internal endpoints.

---

## Example: Testing a Public API

```
🌐 Enter URL or API endpoint: api.github.com/zen
📡 HTTP Method: [1] GET
Add custom headers? (y/N): n
⏱ Request timeout in seconds [10]: 10
🔒 Verify SSL certificate? (Y/n): y
```

Expected output highlights:
- ✅ DNS resolved to GitHub's IPs
- ✅ Port 443 reachable, ~20ms latency
- ✅ Certificate valid, 200+ days remaining, issued by DigiCert
- ✅ 200 OK — request succeeded
- ⚠️ Missing: `Content-Security-Policy` header

---

## Example: Testing a Private / VPN Endpoint

```
🌐 Enter URL or API endpoint: https://internal.company.local:8443/api/health
📡 HTTP Method: [1] GET
Add custom headers? (y/N): y
  Header: Authorization: Bearer eyJhb...
  Header: (blank to finish)
⏱ Request timeout in seconds [10]: 15
🔒 Verify SSL certificate? (Y/n): n   ← skip if self-signed
```

---

## Example: Testing a POST API with JSON Body

```
🌐 Enter URL or API endpoint: https://api.example.com/v1/users
📡 HTTP Method: [2] POST
Add custom headers? (y/N): y
  Header: Authorization: Bearer <token>
Add request body/payload? (y/N): y

  Paste your JSON, then type END:
  {
    "name": "Test User",
    "email": "test@example.com"
  }
  END

⏱ Request timeout in seconds [10]: 10
🔒 Verify SSL certificate? (Y/n): y
```

---

## SSL Certificate Expiry Alerts

| Days remaining | Alert level | Message |
|---|---|---|
| Expired | 🔴 Critical | "Certificate EXPIRED N days ago" |
| < 14 days | 🔴 Critical | "Renew NOW — browsers will warn users" |
| < 30 days | 🟡 Warning | "Renew within 2 weeks" |
| < 60 days | 🟡 Notice | "Plan renewal" |
| 60+ days | ✅ Healthy | Expiry date shown |

---

## HTTP Status Code Coverage

The tool has built-in explanations and fix suggestions for:

| Range | Codes covered |
|-------|--------------|
| 1xx | 100, 101 |
| 2xx | 200, 201, 204, 206 |
| 3xx | 301, 302, 304, 307, 308 |
| 4xx | 400, 401, 403, 404, 405, 406, 408, 409, 410, 413, 415, 422, 429 |
| 5xx | 500, 501, 502, 503, 504 |
| Cloudflare | 521, 522, 524 |

For any other code, the tool shows the raw status and reason phrase.

---

## Environment Safety

The tool detects your Python environment before installing anything:

| Environment | What the tool does |
|---|---|
| venv / virtualenv | Installs packages normally inside the venv |
| conda | Installs via pip inside the conda env |
| pyenv | Installs normally via pyenv's pip |
| Ubuntu system Python | Refuses auto-install, shows you the venv command to use |
| Unknown | Installs with `--user` only (never touches system files) |

`--break-system-packages` is **never used automatically**. It is only shown as a manual option in the help text if all other methods fail.

---

## Package Dependencies

| Package | Purpose | Typical download |
|---------|---------|-----------------|
| `requests` | HTTP requests | ~531 KB |
| `dnspython` | DNS resolution | ~103 KB |
| `colorama` | Coloured terminal output | ~20 KB |
| `tabulate` | Formatted tables | ~30 KB |
| `urllib3` | HTTP connection pooling (via requests) | ~128 KB |
| `certifi` | CA certificate bundle (via requests) | ~163 KB |
| `charset-normalizer` | Encoding detection (via requests) | ~146 KB |
| `idna` | Internationalized domain names (via requests) | ~238 KB |

**Total one-time download:** ~1.6 MB  
**Disk after install:** ~5.8 MB  
**Runtime RAM:** ~35–50 MB while running (released on exit)

All built-in modules (`ssl`, `socket`, `json`, `re`, `datetime`, `subprocess`, etc.) ship with Python — zero extra download.

---

## Troubleshooting

**"externally-managed-environment" error**
You're on Ubuntu 23.04+ using the system Python. Use a venv:
```bash
python3 -m venv ~/.venvs/urldiag
source ~/.venvs/urldiag/bin/activate
python3 url_diagnostics.py
```

**SSL check fails on a self-signed certificate**
Re-run and answer `n` when asked to verify SSL. The tool will still extract and display the certificate details including expiry.

**DNS check fails but the site loads in browser**
Your browser may use a different DNS resolver (e.g. DoH via Cloudflare). Try:
```bash
nslookup yourdomain.com
```
to confirm what your system resolver sees.

**Connection times out on a private/internal URL**
Check VPN, firewall rules, or whether the service is only accessible from certain networks. Increase timeout when prompted.

**"Module not found" after install**
If pip installs to a path not on `sys.path`, restart the tool once. The bootstrap logic adds `~/.local/lib` to the path automatically.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Cancel current input / exit tool |
| `Enter` (blank) | Accept the shown default value |
| `END` (on its own line) | Finish entering a multi-line payload |

---

## License

MIT — free to use, modify, and distribute.
