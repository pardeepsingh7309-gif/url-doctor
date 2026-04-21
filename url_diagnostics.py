#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         URL / API Error Diagnostic Tool v1.0             ║
║   Detects errors, SSL issues, DNS problems & more        ║
╚══════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 0 — SAFE BOOTSTRAP
# Runs BEFORE any third-party import.  Detects the Python environment and
# decides how (or whether) to install missing packages without ever touching
# the system-managed Python or an existing project's venv.
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import os
import shutil
import sysconfig

# ── 0a. Python version guard ───────────────────────────────────────────────────
if sys.version_info < (3, 7):
    print("❌  Python 3.7 or newer is required.")
    print(f"    You are running: Python {sys.version}")
    print("    Fix (Ubuntu): sudo apt install python3.11")
    sys.exit(1)

# ── 0b. Detect which Python environment we are running inside ─────────────────
def _detect_env() -> dict:
    """
    Returns a dict describing the current Python environment so that the
    install logic can make a safe, informed decision.

    Keys
    ----
    kind        : 'venv' | 'conda' | 'pipx' | 'pyenv' | 'system' | 'unknown'
    in_venv     : True if inside *any* virtual environment
    is_system   : True if this is the OS-managed system Python (do NOT touch)
    pip_ok      : True if `pip` module is importable at all
    pip_cmd     : list – the pip command to use  (e.g. [sys.executable, '-m', 'pip'])
    site_pkgs   : path to the writable site-packages for this interpreter
    description : human-readable one-liner
    """
    result = {
        "kind": "unknown",
        "in_venv": False,
        "is_system": False,
        "pip_ok": False,
        "pip_cmd": [sys.executable, "-m", "pip"],
        "site_pkgs": sysconfig.get_path("purelib"),
        "description": "",
    }

    # ── Is pip available? ──────────────────────────────────────────────────────
    try:
        import importlib
        result["pip_ok"] = importlib.util.find_spec("pip") is not None
    except Exception:
        pass

    # ── venv / virtualenv ──────────────────────────────────────────────────────
    in_venv = (
        os.environ.get("VIRTUAL_ENV") is not None          # standard venv / virtualenv
        or os.environ.get("CONDA_DEFAULT_ENV") is not None # conda
        or hasattr(sys, "real_prefix")                     # old virtualenv
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )
    result["in_venv"] = in_venv

    # ── conda ─────────────────────────────────────────────────────────────────
    if os.environ.get("CONDA_DEFAULT_ENV"):
        result["kind"] = "conda"
        result["description"] = (
            f"conda env '{os.environ['CONDA_DEFAULT_ENV']}' "
            f"(prefix: {os.environ.get('CONDA_PREFIX', '?')})"
        )
        return result

    # ── standard venv / virtualenv ────────────────────────────────────────────
    if in_venv:
        result["kind"] = "venv"
        venv_path = os.environ.get("VIRTUAL_ENV") or sys.prefix
        result["description"] = f"venv at {venv_path}"
        return result

    # ── pipx ──────────────────────────────────────────────────────────────────
    if "pipx" in sys.executable or "pipx" in os.environ.get("PATH", ""):
        result["kind"] = "pipx"
        result["description"] = "pipx-managed environment"
        return result

    # ── pyenv ─────────────────────────────────────────────────────────────────
    if os.environ.get("PYENV_VERSION") or ".pyenv" in sys.executable:
        result["kind"] = "pyenv"
        result["description"] = f"pyenv Python at {sys.executable}"
        return result

    # ── system Python (Ubuntu / Debian managed) ───────────────────────────────
    # Heuristic: executable lives under /usr/bin or /usr/lib, AND
    # there is a EXTERNALLY-MANAGED marker file in the stdlib dir.
    stdlib_dir = sysconfig.get_path("stdlib")
    ext_managed_marker = os.path.join(stdlib_dir or "", "EXTERNALLY-MANAGED") if stdlib_dir else ""
    in_usr_bin = sys.executable.startswith("/usr/bin") or sys.executable.startswith("/usr/lib")

    if in_usr_bin and (os.path.exists(ext_managed_marker) or stdlib_dir and "/usr/" in stdlib_dir):
        result["kind"] = "system"
        result["is_system"] = True
        result["description"] = (
            f"Ubuntu/Debian system Python at {sys.executable}\n"
            "    ⚠️  This is the OS-managed interpreter — "
            "packages will NOT be auto-installed here."
        )
        return result

    result["kind"] = "unknown"
    result["description"] = f"Python at {sys.executable}"
    return result


# ── 0c. Pre-flight system-tools check ─────────────────────────────────────────
def _preflight_check() -> dict:
    """
    Checks system tools that the script relies on indirectly.
    Returns a summary dict with 'ok' (bool) and 'report' (list of strings).
    """
    report = []
    all_ok = True

    checks = [
        ("python3",      "Python 3 interpreter"),
        ("pip3",         "pip package manager (pip3)"),
        ("openssl",      "OpenSSL CLI (used by ssl module internally)"),
        ("nslookup",     "DNS lookup tool (fallback info only)"),
        ("curl",         "curl (optional — for cross-check)"),
    ]

    report.append(f"  Python : {sys.executable}  ({sys.version.split()[0]})")

    for cmd, label in checks:
        found = shutil.which(cmd)
        if found:
            report.append(f"  ✅  {label:40s} → {found}")
        else:
            marker = "⚠️ " if cmd in ("curl", "nslookup") else "❌"
            report.append(f"  {marker}  {label:40s} → not found")
            if cmd not in ("curl", "nslookup"):   # optional tools don't fail
                all_ok = False

    # Check built-in ssl module (must exist)
    try:
        import ssl as _ssl
        report.append(f"  ✅  {'ssl module (built-in TLS)':40s} → {_ssl.OPENSSL_VERSION}")
    except ImportError:
        report.append(f"  ❌  {'ssl module (built-in TLS)':40s} → MISSING — rebuild Python with OpenSSL")
        all_ok = False

    # Check socket module
    try:
        import socket as _sock
        report.append(f"  ✅  {'socket module (built-in networking)':40s} → ok")
    except ImportError:
        report.append(f"  ❌  {'socket module':40s} → MISSING")
        all_ok = False

    return {"ok": all_ok, "report": report}


# ── 0d. Safe package installer ────────────────────────────────────────────────
PKG_IMPORT_MAP = {
    "dnspython": "dns",
    "colorama":  "colorama",
    "tabulate":  "tabulate",
    "requests":  "requests",
    "urllib3":   "urllib3",
}

def _try_pip_install(pkg: str, env: dict) -> tuple:
    """
    Installs *pkg* using the safest strategy for the detected environment.
    Returns (success: bool, method_used: str).

    Strategy matrix
    ───────────────
    venv / conda / pyenv   → plain pip install  (isolated, always safe)
    system Python          → REFUSE auto-install; tell user to use a venv
    unknown                → --user install only (never --break-system-packages)
    """
    base = [sys.executable, "-m", "pip", "install", pkg, "--quiet"]

    # ── System Python: refuse to auto-install ─────────────────────────────────
    if env["is_system"]:
        return False, "refused-system-python"

    # ── Inside a venv / conda / pyenv: plain install ──────────────────────────
    if env["in_venv"] or env["kind"] in ("conda", "pyenv"):
        r = subprocess.run(base, capture_output=True, text=True)
        if r.returncode == 0:
            return True, "pip-install"
        return False, f"pip-error: {r.stderr.strip()[:120]}"

    # ── Unknown env: safest option is --user (never touches system files) ─────
    r = subprocess.run(base + ["--user"], capture_output=True, text=True)
    if r.returncode == 0:
        # Ensure ~/.local/lib/.../site-packages is on sys.path this session
        import site
        try:
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.insert(0, user_site)
        except AttributeError:
            pass
        return True, "pip-install --user"

    return False, f"pip-error: {r.stderr.strip()[:120]}"


REQUIRED = ["requests", "colorama", "dnspython", "urllib3", "tabulate"]

def _bootstrap(packages: list, env: dict):
    """
    Check which packages are missing, install what we safely can,
    and print a clear manual-install guide for anything we can't.
    Exits if any required package is unavailable after all attempts.
    """
    missing_before = []
    for pkg in packages:
        imp = PKG_IMPORT_MAP.get(pkg, pkg.replace("-", "_"))
        try:
            __import__(imp)
        except ImportError:
            missing_before.append(pkg)

    if not missing_before:
        print("  ✅ All packages already present — nothing to install.\n")
        return

    print(f"  📋 Missing: {', '.join(missing_before)}\n")

    still_missing = []
    for pkg in missing_before:
        imp = PKG_IMPORT_MAP.get(pkg, pkg.replace("-", "_"))

        if env["is_system"]:
            # Don't even try — just collect and explain below
            still_missing.append((pkg, "system-python-protected"))
            continue

        print(f"  📦 Installing '{pkg}'...", end=" ", flush=True)
        ok_install, method = _try_pip_install(pkg, env)

        if ok_install:
            # Re-verify the import actually works
            try:
                __import__(imp)
                print(f"✅  ({method})")
            except ImportError:
                print(f"⚠️  installed but import failed")
                still_missing.append((pkg, "import-failed-after-install"))
        else:
            print(f"❌  ({method})")
            still_missing.append((pkg, method))

    if still_missing:
        pkgs_str = " ".join(p for p, _ in still_missing)
        print("\n  ❌  The following required packages could not be auto-installed:")
        for pkg, reason in still_missing:
            print(f"       • {pkg}  [{reason}]")
        print()

        if env["is_system"] or any("system" in r for _, r in still_missing):
            print("  ⚠️  You are using the Ubuntu system Python.")
            print("      Auto-installing here would risk breaking system tools.")
            print()
            print("  ✅  RECOMMENDED — run inside a virtual environment:")
            print(f"       python3 -m venv ~/.venvs/urldiag")
            print(f"       source ~/.venvs/urldiag/bin/activate")
            print(f"       pip install {pkgs_str}")
            print(f"       python3 {os.path.abspath(__file__)}")
            print()
            print("  ⚡  Quick one-liner (if you accept the risk):")
            print(f"       pip3 install {pkgs_str} --break-system-packages")
        else:
            print("  👉  Manual install:")
            print(f"       pip3 install {pkgs_str} --user")

        print()
        sys.exit(1)


# ── 0e. Run the pre-flight + bootstrap ────────────────────────────────────────
print()
print("╔══════════════════════════════════════════════════════════╗")
print("║          🔧  Environment Pre-Flight Check                ║")
print("╚══════════════════════════════════════════════════════════╝")

env_info = _detect_env()
preflight = _preflight_check()

print(f"\n  Environment : {env_info['description']}")
print()
for line in preflight["report"]:
    print(line)

if not preflight["ok"]:
    print("\n  ❌  Critical system tools are missing. Fix them before continuing.")
    sys.exit(1)

print()
print("─" * 62)
print("  📦  Checking Python packages...")
print("─" * 62)

_bootstrap(REQUIRED, env_info)
print("  ✅ All packages ready.\n")

# ─── Imports ────────────────────────────────────────────────────────────────────
import ssl
import socket
import datetime
import json
import re
import time
import warnings

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
import dns.resolver
import dns.exception
from colorama import init, Fore, Style, Back
from tabulate import tabulate

warnings.filterwarnings("ignore", category=InsecureRequestWarning)
init(autoreset=True)

# ═══════════════════════════════════════════════════════════════════════════════
# COLOUR HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def c(text, colour=Fore.WHITE, bold=False):
    return (Style.BRIGHT if bold else "") + colour + str(text) + Style.RESET_ALL

def banner():
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║        🔍  URL / API Error Diagnostic Tool v1.0          ║",
        "║   HTTP • SSL/TLS • DNS • Redirect • Auth • CORS • API    ║",
        "╚══════════════════════════════════════════════════════════╝",
    ]
    for line in lines:
        print(c(line, Fore.CYAN, bold=True))

def section(title):
    print("\n" + c(f"{'─'*4} {title} {'─'*(54-len(title))}", Fore.YELLOW, bold=True))

def ok(msg):    print(c("  ✅ " + msg, Fore.GREEN))
def warn(msg):  print(c("  ⚠️  " + msg, Fore.YELLOW))
def err(msg):   print(c("  ❌ " + msg, Fore.RED))
def info(msg):  print(c("  ℹ️  " + msg, Fore.CYAN))
def tip(msg):   print(c("  💡 " + msg, Fore.MAGENTA))
def sub(msg):   print(c("     " + msg, Fore.WHITE))

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP STATUS CODE KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════════════
HTTP_STATUS_KB = {
    # 1xx
    100: ("Continue",               "Server received request headers; client should proceed.",
          "Normal in chunked uploads. No action needed."),
    101: ("Switching Protocols",    "Server is switching protocol (e.g., HTTP→WebSocket).",
          "Expected for WS upgrades. Ensure client handles WebSocket handshake."),
    # 2xx
    200: ("OK",                     "Request succeeded.",           "No error — response is healthy."),
    201: ("Created",                "Resource created successfully.","Standard for POST endpoints. Check Location header for new resource URI."),
    204: ("No Content",             "Success but no body returned.", "Normal for DELETE/PUT. Don't expect a response body."),
    206: ("Partial Content",        "Range request fulfilled.",      "Normal for file downloads. Verify Range headers."),
    # 3xx
    301: ("Moved Permanently",      "Resource has a new permanent URL.",
          "Update bookmarks/hardcoded URLs. Check Location header. SEO impact: passes link equity."),
    302: ("Found (Temp Redirect)",  "Temporary redirect.",
          "Use 307 to preserve HTTP method. If login loop, check session/cookie config."),
    304: ("Not Modified",           "Cached version is still valid.", "Browser cache is working. No action needed."),
    307: ("Temporary Redirect",     "Temporary redirect preserving method.",
          "Correct behaviour for POST redirects. Verify destination URL."),
    308: ("Permanent Redirect",     "Permanent redirect preserving method.",
          "Update all references to the new URL."),
    # 4xx
    400: ("Bad Request",            "Server couldn't understand the request due to invalid syntax.",
          "Check request body format (JSON/XML malformed?), Content-Type header, required fields, query params."),
    401: ("Unauthorized",           "Authentication is required and has failed or not been provided.",
          "Add/renew Bearer token or API key. Check Authorization header format: 'Bearer <token>'. Verify credentials."),
    403: ("Forbidden",              "Server understood but refuses to authorise.",
          "Check user permissions/roles. IP whitelist? CORS policy? API key has correct scopes?"),
    404: ("Not Found",              "Resource doesn't exist at this URL.",
          "Verify URL path, trailing slashes, case sensitivity. Check API version prefix (v1, v2). Resource may be deleted."),
    405: ("Method Not Allowed",     "HTTP method not supported for this endpoint.",
          "Check API docs for allowed methods. Use OPTIONS request to discover allowed methods."),
    406: ("Not Acceptable",         "Server can't produce a response matching Accept headers.",
          "Adjust Accept header (e.g., application/json). Check server's supported Content-Types."),
    408: ("Request Timeout",        "Server timed out waiting for the request.",
          "Retry with exponential backoff. Check network latency. Increase client timeout. Server may be overloaded."),
    409: ("Conflict",               "Request conflicts with current resource state.",
          "Common on duplicate creation. Check for existing resource first. Handle idempotency keys."),
    410: ("Gone",                   "Resource permanently deleted.",
          "Remove references. Unlike 404, the resource deliberately no longer exists."),
    413: ("Payload Too Large",      "Request body exceeds server limit.",
          "Compress payload, paginate, or use chunked upload. Check server's max_body_size config."),
    415: ("Unsupported Media Type", "Content-Type not supported.",
          "Set correct Content-Type (e.g., application/json). Match what the API expects."),
    422: ("Unprocessable Entity",   "Semantically invalid request (common in REST APIs).",
          "Validate all required fields, data types, enum values. Read error body for field-level details."),
    429: ("Too Many Requests",      "Rate limit exceeded.",
          "Implement exponential backoff. Check Retry-After header. Consider caching responses. Review API rate limits."),
    # 5xx
    500: ("Internal Server Error",  "Generic server-side failure.",
          "Check server logs. Retry after a moment. If persistent, contact API provider. May be a bug."),
    501: ("Not Implemented",        "Server doesn't support the requested functionality.",
          "Feature not available. Check API version or alternative endpoints."),
    502: ("Bad Gateway",            "Upstream server returned an invalid response.",
          "Usually proxy/load-balancer issue. Check if origin server is running. Retry. May be transient."),
    503: ("Service Unavailable",    "Server temporarily unable to handle requests.",
          "Check Retry-After header. Server may be under maintenance or overloaded. Implement retry logic."),
    504: ("Gateway Timeout",        "Upstream server didn't respond in time.",
          "Origin server too slow or down. Increase timeout settings. Check server health. Add caching layer."),
    521: ("Web Server Is Down",     "Cloudflare can't connect to origin.",
          "Ensure origin web server is running and firewall allows Cloudflare IPs."),
    522: ("Connection Timed Out",   "Cloudflare TCP handshake timed out.",
          "Origin server not responding on port 80/443. Check firewall rules."),
    524: ("A Timeout Occurred",     "Cloudflare connected but origin timed out.",
          "Optimise slow requests, increase Cloudflare timeout setting, or add streaming."),
}

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def normalise_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url

def extract_host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or ""

def extract_port(url: str) -> int:
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.port:
        return p.port
    return 443 if url.startswith("https") else 80

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK MODULES
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. DNS Resolution ──────────────────────────────────────────────────────────
def check_dns(host: str) -> dict:
    result = {"passed": False, "ip": None, "error": None, "records": []}
    try:
        answers = dns.resolver.resolve(host, "A")
        result["ip"] = str(answers[0])
        result["records"] = [str(r) for r in answers]
        result["passed"] = True
    except dns.exception.NXDOMAIN:
        result["error"] = "NXDOMAIN — domain does not exist"
    except dns.exception.Timeout:
        result["error"] = "DNS query timed out"
    except dns.resolver.NoAnswer:
        result["error"] = "No A-record found for this domain"
    except Exception as e:
        result["error"] = str(e)
    return result

# ── 2. TCP Connectivity ────────────────────────────────────────────────────────
def check_tcp(host: str, port: int, timeout: int = 5) -> dict:
    result = {"passed": False, "latency_ms": None, "error": None}
    try:
        t0 = time.time()
        with socket.create_connection((host, port), timeout=timeout):
            result["latency_ms"] = round((time.time() - t0) * 1000, 1)
            result["passed"] = True
    except socket.timeout:
        result["error"] = f"TCP connection to {host}:{port} timed out"
    except ConnectionRefusedError:
        result["error"] = f"Connection refused on port {port} — nothing listening?"
    except Exception as e:
        result["error"] = str(e)
    return result

# ── 3. SSL / TLS Certificate ──────────────────────────────────────────────────
def check_ssl(host: str, port: int = 443) -> dict:
    result = {
        "passed": False, "valid": False, "expiry": None, "days_left": None,
        "issuer": None, "subject": None, "san": [], "error": None,
        "self_signed": False, "protocol": None,
    }
    if port != 443 and port != 8443:
        # Try anyway but mark port
        pass
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((host, port), timeout=8),
                             server_hostname=host) as s:
            cert = s.getpeercert()
            result["protocol"] = s.version()

            # Expiry
            exp_str = cert.get("notAfter", "")
            if exp_str:
                exp_dt = datetime.datetime.strptime(exp_str, "%b %d %H:%M:%S %Y %Z")
                result["expiry"] = exp_dt.strftime("%Y-%m-%d")
                result["days_left"] = (exp_dt - datetime.datetime.utcnow()).days

            # Subject / Issuer
            subject = dict(x[0] for x in cert.get("subject", []))
            issuer  = dict(x[0] for x in cert.get("issuer",  []))
            result["subject"] = subject.get("commonName", "unknown")
            result["issuer"]  = issuer.get("organizationName", issuer.get("commonName", "unknown"))

            # SAN
            san_raw = cert.get("subjectAltName", [])
            result["san"] = [v for t, v in san_raw if t == "DNS"]

            result["valid"] = True
            result["passed"] = True

    except ssl.SSLCertVerificationError as e:
        result["error"] = f"SSL verification failed: {e.reason}"
        result["self_signed"] = "self signed" in str(e).lower() or "unable to get local issuer" in str(e).lower()
        # Still try to get cert info without verification
        try:
            ctx2 = ssl.create_default_context()
            ctx2.check_hostname = False
            ctx2.verify_mode = ssl.CERT_NONE
            with ctx2.wrap_socket(socket.create_connection((host, port), timeout=8),
                                  server_hostname=host) as s2:
                der = s2.getpeercert(binary_form=True)
                cert2 = s2.getpeercert()
                result["protocol"] = s2.version()
                exp_str = cert2.get("notAfter", "")
                if exp_str:
                    exp_dt = datetime.datetime.strptime(exp_str, "%b %d %H:%M:%S %Y %Z")
                    result["expiry"] = exp_dt.strftime("%Y-%m-%d")
                    result["days_left"] = (exp_dt - datetime.datetime.utcnow()).days
                subject2 = dict(x[0] for x in cert2.get("subject", []))
                issuer2  = dict(x[0] for x in cert2.get("issuer",  []))
                result["subject"] = subject2.get("commonName", "unknown")
                result["issuer"]  = issuer2.get("organizationName", issuer2.get("commonName", "unknown"))
        except Exception:
            pass

    except ssl.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except socket.timeout:
        result["error"] = "SSL handshake timed out"
    except ConnectionRefusedError:
        result["error"] = f"Port {port} refused — SSL not available"
    except Exception as e:
        result["error"] = str(e)
    return result

# ── 4. HTTP Request ────────────────────────────────────────────────────────────
def make_http_request(url: str, method: str, headers: dict,
                      payload: str, timeout: int, verify_ssl: bool) -> dict:
    result = {
        "status": None, "reason": None, "latency_ms": None,
        "headers": {}, "body_snippet": "", "redirect_chain": [],
        "error": None, "error_type": None,
    }
    body_data = None
    if payload:
        try:
            body_data = json.loads(payload)
        except json.JSONDecodeError:
            body_data = payload

    try:
        t0 = time.time()
        resp = requests.request(
            method, url,
            headers=headers,
            json=body_data if isinstance(body_data, dict) else None,
            data=body_data if isinstance(body_data, str) else None,
            timeout=timeout,
            verify=verify_ssl,
            allow_redirects=True,
        )
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        result["status"] = resp.status_code
        result["reason"] = resp.reason
        result["headers"] = dict(resp.headers)
        result["redirect_chain"] = [r.url for r in resp.history] + [resp.url]
        try:
            result["body_snippet"] = resp.text[:600]
        except Exception:
            result["body_snippet"] = ""

    except requests.exceptions.SSLError as e:
        result["error"] = str(e)
        result["error_type"] = "SSL_ERROR"
    except requests.exceptions.ConnectionError as e:
        result["error"] = str(e)
        result["error_type"] = "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {timeout}s"
        result["error_type"] = "TIMEOUT"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "Too many redirects (>30)"
        result["error_type"] = "REDIRECT_LOOP"
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = "UNKNOWN"
    return result

# ── 5. CORS Analysis ──────────────────────────────────────────────────────────
def analyse_cors(resp_headers: dict) -> dict:
    acao  = resp_headers.get("Access-Control-Allow-Origin", "")
    acam  = resp_headers.get("Access-Control-Allow-Methods", "")
    acah  = resp_headers.get("Access-Control-Allow-Headers", "")
    acac  = resp_headers.get("Access-Control-Allow-Credentials", "")
    notes = []
    if not acao:
        notes.append("No CORS headers — browser cross-origin requests will be blocked.")
    elif acao == "*" and acac.lower() == "true":
        notes.append("⚠️  Wildcard origin (*) with Allow-Credentials=true is INVALID and will be rejected by browsers.")
    elif acao == "*":
        notes.append("Public API — any origin allowed (no credentials).")
    else:
        notes.append(f"Restricted to origin: {acao}")
    return {"origin": acao, "methods": acam, "headers": acah, "notes": notes}

# ── 6. Security Headers ───────────────────────────────────────────────────────
SECURITY_HEADERS = {
    "Strict-Transport-Security": ("HSTS — forces HTTPS",
                                  "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains"),
    "X-Content-Type-Options":    ("Prevents MIME sniffing",
                                  "Add: X-Content-Type-Options: nosniff"),
    "X-Frame-Options":           ("Clickjacking protection",
                                  "Add: X-Frame-Options: DENY or SAMEORIGIN"),
    "Content-Security-Policy":   ("XSS / injection protection",
                                  "Add a strict CSP policy."),
    "Referrer-Policy":           ("Controls referrer leakage",
                                  "Add: Referrer-Policy: strict-origin-when-cross-origin"),
    "Permissions-Policy":        ("Limits browser feature access",
                                  "Add Permissions-Policy to restrict camera/mic/geo."),
}

def check_security_headers(resp_headers: dict) -> list:
    missing = []
    for hdr, (desc, fix) in SECURITY_HEADERS.items():
        if hdr not in resp_headers:
            missing.append((hdr, desc, fix))
    return missing

# ═══════════════════════════════════════════════════════════════════════════════
# REPORT PRINTER
# ═══════════════════════════════════════════════════════════════════════════════
def print_report(url, method, dns_r, tcp_r, ssl_r, http_r,
                 cors_r, sec_missing, custom_headers):
    host = extract_host(url)
    port = extract_port(url)

    print()
    print(c("═"*62, Fore.CYAN, bold=True))
    print(c(f"  DIAGNOSTIC REPORT FOR: {url}", Fore.WHITE, bold=True))
    print(c(f"  Method: {method}  |  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Fore.WHITE))
    print(c("═"*62, Fore.CYAN, bold=True))

    # ── DNS ────────────────────────────────────────────────────────────────────
    section("1 · DNS RESOLUTION")
    if dns_r["passed"]:
        ok(f"Domain resolved → {', '.join(dns_r['records'])}")
    else:
        err(f"DNS failed: {dns_r['error']}")
        tip("Fix: Verify domain spelling. Check registrar DNS records. Try 'nslookup' locally.")
        if "NXDOMAIN" in str(dns_r["error"]):
            tip("NXDOMAIN means the domain doesn't exist at all in DNS.")

    # ── TCP ────────────────────────────────────────────────────────────────────
    section("2 · TCP CONNECTIVITY")
    if tcp_r["passed"]:
        ok(f"Port {port} reachable  |  Latency: {tcp_r['latency_ms']} ms")
        if tcp_r["latency_ms"] and tcp_r["latency_ms"] > 500:
            warn("High latency detected. Server may be geographically distant or overloaded.")
    else:
        err(f"TCP failed: {tcp_r['error']}")
        tip("Fix: Check firewall rules, VPN, private network access. Is the server running?")

    # ── SSL ────────────────────────────────────────────────────────────────────
    section("3 · SSL / TLS CERTIFICATE")
    if url.startswith("http://"):
        warn("HTTP (not HTTPS) — no SSL to analyse. Consider enabling HTTPS.")
    elif ssl_r["error"] and not ssl_r["expiry"]:
        err(f"SSL error: {ssl_r['error']}")
        if ssl_r.get("self_signed"):
            tip("Self-signed certificate detected. Browser/clients will reject this.")
            tip("Fix: Obtain a free cert from Let's Encrypt (certbot) or a paid CA.")
        else:
            tip("Fix: Verify cert chain is complete, not expired, and CN/SAN matches the hostname.")
    else:
        if ssl_r["valid"]:
            ok(f"Certificate valid  |  Issuer: {ssl_r['issuer']}")
        else:
            warn(f"Certificate issue: {ssl_r['error']}")
            if ssl_r.get("self_signed"):
                tip("Self-signed certificate — not trusted by browsers/OS.")

        if ssl_r["protocol"]:
            proto = ssl_r["protocol"]
            if proto in ("TLSv1", "TLSv1.1", "SSLv3"):
                warn(f"Outdated protocol: {proto}. Upgrade to TLS 1.2+ immediately.")
                tip("Fix: Configure server (Nginx/Apache) to disable TLS < 1.2.")
            else:
                ok(f"Protocol: {proto}")

        if ssl_r["subject"]:
            sub(f"Subject CN : {ssl_r['subject']}")
        if ssl_r["san"]:
            sub(f"SANs       : {', '.join(ssl_r['san'][:5])}" +
                (f" (+{len(ssl_r['san'])-5} more)" if len(ssl_r["san"]) > 5 else ""))
        if ssl_r["expiry"]:
            days = ssl_r["days_left"]
            expiry_str = ssl_r["expiry"]
            if days is None:
                info(f"Expiry: {expiry_str}")
            elif days < 0:
                err(f"Certificate EXPIRED {abs(days)} days ago ({expiry_str})!")
                tip("Fix: Renew immediately. Use 'certbot renew' or dashboard of your CA.")
            elif days <= 14:
                err(f"Certificate expires in {days} days ({expiry_str}) — CRITICAL!")
                tip("Fix: Renew NOW. Browsers will show scary warnings when it expires.")
            elif days <= 30:
                warn(f"Certificate expires in {days} days ({expiry_str}) — renew soon.")
                tip("Fix: Renew within the next 2 weeks to avoid service interruption.")
            elif days <= 60:
                warn(f"Certificate expires in {days} days ({expiry_str}) — plan renewal.")
            else:
                ok(f"Certificate expires in {days} days ({expiry_str}) — healthy.")

    # ── HTTP ───────────────────────────────────────────────────────────────────
    section("4 · HTTP RESPONSE")
    if http_r["error"]:
        err(f"Request failed: {http_r['error']}")
        etype = http_r.get("error_type", "")
        if etype == "SSL_ERROR":
            tip("SSL handshake failed. The cert may be invalid, self-signed, or expired.")
            tip("Try re-running and choosing 'skip SSL verification' to confirm connectivity.")
        elif etype == "CONNECTION_ERROR":
            tip("Could not reach the server. Check if URL is correct, server is up, or VPN is needed.")
        elif etype == "TIMEOUT":
            tip("Server took too long to respond. It may be overloaded or the URL hangs.")
            tip("Fix: Increase timeout, check server health, add caching.")
        elif etype == "REDIRECT_LOOP":
            tip("Redirect loop detected. Check web server / load balancer redirect rules.")
        else:
            tip("Unexpected error. Check URL format and network connectivity.")
    else:
        code = http_r["status"]
        colour = Fore.GREEN if code < 300 else (Fore.YELLOW if code < 400 else Fore.RED)
        print(c(f"  ⬤  Status: {code} {http_r['reason']}", colour, bold=True))

        if code in HTTP_STATUS_KB:
            name, desc, fix = HTTP_STATUS_KB[code]
            sub(f"What it means : {desc}")
            tip(f"Suggested fix : {fix}")
        else:
            info(f"Unknown status code {code}. Consult RFC 9110 or API docs.")

        # Latency
        lat = http_r["latency_ms"]
        if lat:
            if lat < 200:   ok(f"Response time: {lat} ms  (fast)")
            elif lat < 800: warn(f"Response time: {lat} ms  (acceptable)")
            else:           err(f"Response time: {lat} ms  (slow — investigate server performance)")

        # Redirect chain
        chain = http_r.get("redirect_chain", [])
        if len(chain) > 1:
            info(f"Redirect chain ({len(chain)-1} hop(s)):")
            for i, u in enumerate(chain):
                sub(f"  {'→ ' if i else '  '}{u}")
            if len(chain) > 4:
                warn("Many redirects — consider consolidating to a single redirect.")

        # Auth hints
        resp_hdrs = http_r["headers"]
        if code == 401:
            www_auth = resp_hdrs.get("WWW-Authenticate", "")
            if www_auth:
                info(f"Server expects: {www_auth}")
                tip("Add matching Authorization header (Bearer token / Basic auth / API key).")
        if code == 429:
            retry_after = resp_hdrs.get("Retry-After", "")
            if retry_after:
                info(f"Retry-After: {retry_after} seconds")

        # Body snippet
        body = http_r.get("body_snippet", "").strip()
        if body and code >= 400:
            section("   Error Body Snippet")
            # Try to pretty-print JSON
            try:
                parsed = json.loads(body)
                body = json.dumps(parsed, indent=2)[:500]
            except Exception:
                pass
            for line in body.splitlines()[:12]:
                sub("  " + line)

    # ── CORS ───────────────────────────────────────────────────────────────────
    if cors_r:
        section("5 · CORS ANALYSIS")
        for note in cors_r["notes"]:
            if "block" in note.lower() or "invalid" in note.lower():
                warn(note)
            elif "⚠️" in note:
                warn(note)
            else:
                ok(note)
        if cors_r["methods"]:
            info(f"Allowed Methods : {cors_r['methods']}")
        if cors_r["headers"]:
            info(f"Allowed Headers : {cors_r['headers']}")

    # ── Security Headers ───────────────────────────────────────────────────────
    if sec_missing is not None:
        section("6 · SECURITY HEADERS")
        if not sec_missing:
            ok("All recommended security headers are present.")
        else:
            warn(f"{len(sec_missing)} security header(s) missing:")
            for hdr, desc, fix in sec_missing:
                sub(f"  • {hdr} — {desc}")
                tip(f"    {fix}")

    # ── Server Info ────────────────────────────────────────────────────────────
    if http_r.get("headers"):
        section("7 · SERVER METADATA")
        rh = http_r["headers"]
        rows = []
        for key in ["Server", "X-Powered-By", "Content-Type", "Cache-Control",
                    "CF-Ray", "X-Request-Id", "X-RateLimit-Limit",
                    "X-RateLimit-Remaining", "X-RateLimit-Reset"]:
            if key in rh:
                rows.append([key, rh[key]])
        if rows:
            print(tabulate(rows, tablefmt="simple", headers=["Header", "Value"]))
        else:
            info("No additional server metadata headers found.")

    print()
    print(c("═"*62, Fore.CYAN, bold=True))
    print(c("  ✅  Diagnosis complete.", Fore.GREEN, bold=True))
    print(c("═"*62, Fore.CYAN, bold=True))
    print()

# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE PROMPT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def prompt(msg, default=""):
    try:
        val = input(c(msg, Fore.CYAN)).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

def choose(msg, options, default="1"):
    for i, opt in enumerate(options, 1):
        print(c(f"  [{i}] {opt}", Fore.WHITE))
    while True:
        choice = prompt(f"{msg} [{default}]: ", default)
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        elif choice == default:
            return options[int(default) - 1]
        print(c("  ⚠️  Invalid choice. Try again.", Fore.YELLOW))

def get_custom_headers() -> dict:
    headers = {}
    print(c("\n  Add custom headers? (useful for Authorization, API keys, etc.)", Fore.WHITE))
    print(c("  Format: Header-Name: value  (blank line to finish)", Fore.WHITE))
    while True:
        line = prompt("  Header: ")
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
            ok(f"Added: {k.strip()}")
        else:
            warn("Format must be 'Header-Name: value'")
    return headers

def get_payload() -> str:
    print(c("\n  Enter request body/payload (JSON or plain text).", Fore.WHITE))
    print(c("  Paste all lines, then type END on its own line (Ctrl+C to cancel):", Fore.WHITE))
    lines = []
    try:
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip().upper() == "END":
                break
            lines.append(line)
    except KeyboardInterrupt:
        print()
        warn("Payload cancelled — continuing with empty body.")
        return ""
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INTERACTIVE LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    os.system("cls" if os.name == "nt" else "clear")
    banner()

    while True:
        print()
        print(c("─"*62, Fore.YELLOW))
        print(c("  NEW DIAGNOSTIC SESSION", Fore.WHITE, bold=True))
        print(c("─"*62, Fore.YELLOW))

        # ── URL ──────────────────────────────────────────────────────────────
        url_raw = prompt("\n  🌐 Enter URL or API endpoint: ")
        if not url_raw:
            warn("No URL entered. Please try again.")
            continue
        url = normalise_url(url_raw)
        host = extract_host(url)
        port = extract_port(url)
        if not host:
            err("Could not parse a hostname from the URL. Please check and try again.")
            continue
        info(f"Parsed host: {host}  port: {port}")

        # ── HTTP Method ───────────────────────────────────────────────────────
        print()
        method = choose("  📡 HTTP Method:", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        print()

        # ── Custom Headers ────────────────────────────────────────────────────
        add_hdrs = prompt("  Add custom headers? (y/N): ", "n").lower()
        custom_headers = {}
        if add_hdrs == "y":
            custom_headers = get_custom_headers()
        # Default JSON content type for POST/PUT/PATCH
        if method in ("POST", "PUT", "PATCH") and "Content-Type" not in custom_headers:
            custom_headers.setdefault("Content-Type", "application/json")

        # ── Payload ───────────────────────────────────────────────────────────
        payload = ""
        if method in ("POST", "PUT", "PATCH"):
            add_body = prompt("  Add request body/payload? (y/N): ", "n").lower()
            if add_body == "y":
                payload = get_payload()

        # ── Timeout ───────────────────────────────────────────────────────────
        timeout_str = prompt("  ⏱  Request timeout in seconds [10]: ", "10")
        try:
            timeout = int(timeout_str)
        except ValueError:
            timeout = 10

        # ── SSL Verification ──────────────────────────────────────────────────
        verify_ssl_str = prompt("  🔒 Verify SSL certificate? (Y/n): ", "y").lower()
        verify_ssl = verify_ssl_str != "n"

        # ── Run Checks ────────────────────────────────────────────────────────
        print()
        print(c("  ⟳  Running diagnostics...", Fore.YELLOW, bold=True))

        print(c("  [1/5] DNS lookup...", Fore.WHITE))
        dns_r = check_dns(host)

        print(c("  [2/5] TCP connect...", Fore.WHITE))
        tcp_r = check_tcp(host, port)

        ssl_r = {"passed": False, "valid": False, "expiry": None,
                 "days_left": None, "issuer": None, "subject": None,
                 "san": [], "error": None, "self_signed": False, "protocol": None}
        if url.startswith("https"):
            print(c("  [3/5] SSL/TLS certificate...", Fore.WHITE))
            ssl_r = check_ssl(host, port)
        else:
            print(c("  [3/5] SSL/TLS — skipped (HTTP).", Fore.WHITE))

        print(c("  [4/5] HTTP request...", Fore.WHITE))
        http_r = make_http_request(url, method, custom_headers, payload, timeout, verify_ssl)

        cors_r = None
        sec_missing = None
        if http_r.get("headers"):
            print(c("  [5/5] CORS & security headers...", Fore.WHITE))
            cors_r = analyse_cors(http_r["headers"])
            sec_missing = check_security_headers(http_r["headers"])
        else:
            print(c("  [5/5] CORS & security headers — no response to analyse.", Fore.WHITE))

        print_report(url, method, dns_r, tcp_r, ssl_r, http_r,
                     cors_r, sec_missing, custom_headers)

        # ── Repeat? ────────────────────────────────────────────────────────────
        again = prompt("  Run another diagnostic? (Y/n): ", "y").lower()
        if again == "n":
            print(c("\n  👋  Goodbye!\n", Fore.CYAN, bold=True))
            break

if __name__ == "__main__":
    main()
