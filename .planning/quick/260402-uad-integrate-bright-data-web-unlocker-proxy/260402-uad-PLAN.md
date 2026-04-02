---
phase: quick
plan: 260402-uad
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/scrapers/proxy.py
  - backend/app/config.py
  - backend/app/scrapers/yad2.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Yad2 Playwright fallback routes traffic through Bright Data Web Unlocker proxy when env vars are set"
    - "Yad2 scraper works unchanged when proxy env vars are absent (graceful degradation)"
    - "Other scrapers can import and use the proxy config with a one-line call"
  artifacts:
    - path: "backend/app/scrapers/proxy.py"
      provides: "Shared proxy config helper"
      exports: ["get_proxy_launch_args"]
    - path: "backend/app/config.py"
      provides: "Bright Data env var bindings"
      contains: "bright_data_host"
    - path: "backend/app/scrapers/yad2.py"
      provides: "Proxy-enabled Playwright browser launch"
      contains: "get_proxy_launch_args"
  key_links:
    - from: "backend/app/scrapers/yad2.py"
      to: "backend/app/scrapers/proxy.py"
      via: "import get_proxy_launch_args"
      pattern: "from app\\.scrapers\\.proxy import"
    - from: "backend/app/scrapers/proxy.py"
      to: "backend/app/config.py"
      via: "reads settings.bright_data_*"
      pattern: "settings\\.bright_data"
---

<objective>
Integrate Bright Data Web Unlocker proxy into the Yad2 Playwright scraper fallback path to automatically bypass CAPTCHA/bot-detection.

Purpose: Yad2's ShieldSquare CAPTCHA blocks the headless Playwright fallback. Bright Data Web Unlocker handles CAPTCHA solving transparently via its proxy, eliminating manual intervention.

Output: A shared proxy config module (`proxy.py`) and updated Yad2 scraper that routes Playwright traffic through the proxy when credentials are configured.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@backend/app/config.py
@backend/app/scrapers/yad2.py
@backend/app/scrapers/base.py

<interfaces>
<!-- Key types and contracts the executor needs -->

From backend/app/config.py:
```python
class Settings(BaseSettings):
    # ... existing fields ...
    # New fields to add:
    # bright_data_host: str = ""
    # bright_data_user: str = ""
    # bright_data_pass: str = ""

settings = Settings()
```

From backend/app/scrapers/yad2.py (Playwright fallback — the function to modify):
```python
async def fetch_yad2_browser(url: str) -> list[dict]:
    # Line 224: launches persistent context via p.chromium.launch_persistent_context(...)
    # This is where proxy config must be injected
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add proxy config to Settings and create shared proxy helper</name>
  <files>backend/app/config.py, backend/app/scrapers/proxy.py</files>
  <action>
1. In `backend/app/config.py`, add three new optional fields to the `Settings` class (after the scheduler settings block):

```python
# Bright Data Web Unlocker proxy (optional — enables CAPTCHA bypass)
bright_data_host: str = ""   # e.g. "brd.superproxy.io:33335"
bright_data_user: str = ""   # e.g. "brd-customer-xxx-zone-web_unlocker1"
bright_data_pass: str = ""
```

All three default to empty string so the app works without them.

2. Create `backend/app/scrapers/proxy.py` with a single helper function:

```python
"""Shared Bright Data Web Unlocker proxy configuration.

Any scraper using Playwright can call get_proxy_launch_args() to get
the proxy kwarg dict for browser.launch() or launch_persistent_context().

When BRIGHT_DATA_HOST/USER/PASS env vars are unset, returns empty dict
(no proxy — graceful degradation).

IMPORTANT: Target URLs passed to page.goto() MUST use http:// (not https://)
when the proxy is active. The Web Unlocker handles SSL termination itself.
"""

from app.config import settings


def get_proxy_launch_args() -> dict:
    """Return Playwright-compatible proxy kwargs for browser launch.

    Returns {"proxy": {"server": ..., "username": ..., "password": ...}}
    when all three Bright Data env vars are configured.
    Returns {} when any env var is missing (proxy disabled).

    Usage:
        browser = await p.chromium.launch(**get_proxy_launch_args())
        # or
        context = await p.chromium.launch_persistent_context(
            user_data_dir, **get_proxy_launch_args()
        )
    """
    host = settings.bright_data_host
    user = settings.bright_data_user
    password = settings.bright_data_pass

    if not all([host, user, password]):
        return {}

    return {
        "proxy": {
            "server": host,
            "username": user,
            "password": password,
        }
    }


def is_proxy_enabled() -> bool:
    """Check if Bright Data proxy is fully configured."""
    return bool(
        settings.bright_data_host
        and settings.bright_data_user
        and settings.bright_data_pass
    )
```

The helper returns a dict that can be unpacked directly into `launch()` or `launch_persistent_context()` kwargs via `**get_proxy_launch_args()`. When empty, it has zero effect on the call.
  </action>
  <verify>
    <automated>cd /Users/shahafwieder/HouseFinder/backend && python -c "from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled; args = get_proxy_launch_args(); assert args == {}, f'Expected empty dict when no env vars, got {args}'; assert not is_proxy_enabled(); print('OK: proxy helper works, returns empty dict when unconfigured')"</automated>
  </verify>
  <done>proxy.py exists with get_proxy_launch_args() and is_proxy_enabled(). Settings has bright_data_host/user/pass fields. Helper returns empty dict when env vars are unset.</done>
</task>

<task type="auto">
  <name>Task 2: Wire proxy into Yad2 Playwright fallback and use http:// scheme</name>
  <files>backend/app/scrapers/yad2.py</files>
  <action>
Modify `fetch_yad2_browser()` in `backend/app/scrapers/yad2.py`:

1. Add import at top of file (with other imports):
   ```python
   from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled
   ```

2. In `fetch_yad2_browser()`, inject proxy args into BOTH `launch_persistent_context` calls (the initial one at ~line 225 and the captcha-retry one at ~line 259):

   Change:
   ```python
   context = await p.chromium.launch_persistent_context(
       user_data_dir=user_data_dir,
       headless=True,
       ...
   )
   ```
   To:
   ```python
   context = await p.chromium.launch_persistent_context(
       user_data_dir=user_data_dir,
       headless=True,
       locale="he-IL",
       viewport={"width": 1280, "height": 800},
       extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
       **get_proxy_launch_args(),
   )
   ```

   The `**get_proxy_launch_args()` unpacks to nothing when proxy is disabled, or adds the `proxy=` kwarg when configured.

3. URL scheme handling — the Web Unlocker requires `http://` not `https://`. In `run_yad2_scraper()`, where the fallback URL is constructed (~line 507), add scheme conversion when proxy is active:

   After the `url = (...)` block, add:
   ```python
   if is_proxy_enabled():
       url = url.replace("https://", "http://", 1)
       logger.info("[yad2] Proxy active — using http:// scheme for Web Unlocker")
   ```

4. Add a log line at the start of `fetch_yad2_browser()` indicating proxy status:
   ```python
   if is_proxy_enabled():
       logger.info("[yad2] Bright Data Web Unlocker proxy enabled for Playwright")
   ```

5. The CAPTCHA detection block (lines 251-293) can remain as-is — with the proxy, CAPTCHAs should be solved automatically, but keeping the detection as a safety net is good. The proxy args are already injected into the retry context launch via step 2.

Do NOT change `fetch_yad2_api()` (the httpx path) — the proxy is only needed for the Playwright browser path where CAPTCHA appears.
  </action>
  <verify>
    <automated>cd /Users/shahafwieder/HouseFinder/backend && python -c "from app.scrapers.yad2 import fetch_yad2_browser, run_yad2_scraper; from app.scrapers.proxy import get_proxy_launch_args; print('OK: imports resolve, no syntax errors')" && python -c "import ast; ast.parse(open('app/scrapers/yad2.py').read()); print('OK: yad2.py parses without errors')"</automated>
  </verify>
  <done>Yad2 Playwright fallback injects proxy args via **get_proxy_launch_args() in both browser launch calls. URL scheme is downgraded to http:// when proxy is active. Proxy status is logged. httpx path is untouched.</done>
</task>

</tasks>

<verification>
1. Without env vars: `cd backend && python -c "from app.scrapers.proxy import get_proxy_launch_args; assert get_proxy_launch_args() == {}"` returns empty dict
2. Module imports cleanly: `cd backend && python -c "from app.scrapers.yad2 import run_yad2_scraper"` no errors
3. AST valid: `cd backend && python -c "import ast; ast.parse(open('app/scrapers/yad2.py').read()); ast.parse(open('app/scrapers/proxy.py').read())"` no errors
</verification>

<success_criteria>
- proxy.py provides get_proxy_launch_args() returning Playwright-compatible proxy dict
- Yad2 Playwright fallback uses proxy when BRIGHT_DATA_* env vars are set
- Yad2 scraper works identically when env vars are absent (no behavior change)
- URL scheme is http:// when proxy is active (Web Unlocker requirement)
- Future scrapers can `from app.scrapers.proxy import get_proxy_launch_args` with no additional setup
</success_criteria>

<output>
After completion, create `.planning/quick/260402-uad-integrate-bright-data-web-unlocker-proxy/260402-uad-SUMMARY.md`
</output>
