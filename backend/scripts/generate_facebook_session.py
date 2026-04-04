#!/usr/bin/env python3
"""One-time script to generate a Facebook session file via automated login.

Usage:
    FB_EMAIL=you@example.com FB_PASSWORD=yourpass python scripts/generate_facebook_session.py [output_path]

Default output: /data/facebook_session.json

Logs in to Facebook using credentials from environment variables, waits for
the home feed to confirm success, then saves Playwright storage_state
(cookies + localStorage) to the output path.
Both facebook_groups.py and facebook_marketplace.py load this file at runtime.
"""
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

DEFAULT_OUTPUT = "/data/facebook_session.json"


async def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    email = os.environ.get("FB_EMAIL", "").strip()
    password = os.environ.get("FB_PASSWORD", "").strip()
    if not email or not password:
        print("ERROR: FB_EMAIL and FB_PASSWORD environment variables must be set.")
        sys.exit(1)

    print(f"Logging in to Facebook as {email} ...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="he-IL",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await context.new_page()
        await page.goto("https://www.facebook.com/login/", wait_until="networkidle", timeout=60_000)
        print(f"Page loaded: {page.url}")

        # Dismiss cookie consent dialog if present (use JS — Hebrew text selector is unreliable)
        try:
            dismissed = await page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const btn = buttons.find(b =>
                        b.textContent.includes('לאפשר') ||
                        b.textContent.includes('Allow all') ||
                        b.textContent.includes('Accept all') ||
                        b.textContent.includes('Accept')
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }
            """)
            if dismissed:
                print("Cookie dialog dismissed via JS.")
                await page.wait_for_timeout(1_500)
            else:
                print("No cookie dialog found.")
        except Exception as e:
            print(f"Cookie dismiss error: {e}")

        await page.screenshot(path="/tmp/fb_login_page.png")
        print("Screenshot saved to /tmp/fb_login_page.png")

        # Try multiple selectors — Facebook changes its DOM occasionally
        email_sel = "input[name='email'], #email, input[type='email']"
        pass_sel = "input[name='pass'], #pass, input[type='password']"

        await page.wait_for_selector(email_sel, timeout=15_000)
        await page.fill(email_sel, email)
        await page.fill(pass_sel, password)
        await page.click("button[name='login'], [data-testid='royal_login_button'], button[type='submit']")

        # Wait up to 30s for redirect away from /login — indicates success or 2FA
        try:
            await page.wait_for_url(
                lambda url: "/login" not in url and "checkpoint" not in url,
                timeout=30_000,
            )
            print("Login successful — saving session ...")
        except Exception:
            current = page.url
            if "checkpoint" in current or "two_step" in current:
                print(f"2FA or checkpoint detected at: {current}")
                print("Complete the verification in the browser, then the script will continue automatically.")
                # Wait up to 2 minutes for manual 2FA completion
                try:
                    await page.wait_for_url(
                        lambda url: "/login" not in url and "checkpoint" not in url and "two_step" not in url,
                        timeout=120_000,
                    )
                    print("Verification complete — saving session ...")
                except Exception:
                    print(f"Timed out waiting for verification. Current URL: {page.url}")
                    await browser.close()
                    sys.exit(1)
            else:
                print(f"Login may have failed. Current URL: {current}")
                await browser.close()
                sys.exit(1)

        await context.storage_state(path=str(output))
        print(f"Session saved to {output_path}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
