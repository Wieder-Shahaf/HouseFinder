#!/usr/bin/env python3
"""One-time script to generate a Facebook session file via automated login.

Usage:
    FB_EMAIL=you@example.com FB_PASSWORD=yourpass python scripts/generate_facebook_session.py [output_path]

Default output: /data/facebook_session.json
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
        await page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=60_000)
        print(f"Page loaded: {page.url}")

        # Remove the cookie consent overlay from the DOM entirely
        removed = await page.evaluate("""
            () => {
                // The modal overlay that intercepts all pointer events
                const overlay = document.querySelector('.x1n2onr6.x1vjfegm');
                if (overlay) { overlay.remove(); return 'overlay'; }
                // Fallback: remove any element with role="dialog"
                const dialog = document.querySelector('[role="dialog"]');
                if (dialog) { dialog.remove(); return 'dialog'; }
                return null;
            }
        """)
        print(f"Overlay removed: {removed}")
        await page.wait_for_timeout(500)

        await page.screenshot(path="/tmp/fb_login_page.png")
        print("Screenshot saved.")

        # Fill credentials via JS — bypasses any overlay intercepting pointer events
        email_sel = "input[name='email']"
        await page.wait_for_selector(email_sel, timeout=15_000)

        await page.evaluate(f"""
            () => {{
                const email = document.querySelector("input[name='email']");
                const pass = document.querySelector("input[name='pass']");
                const nativeInput = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInput.call(email, {repr(email)});
                email.dispatchEvent(new Event('input', {{ bubbles: true }}));
                nativeInput.call(pass, {repr(password)});
                pass.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        """)
        print("Credentials filled via JS.")

        await page.screenshot(path="/tmp/fb_filled.png")

        # Submit the form directly
        await page.evaluate("""
            () => {
                const form = document.querySelector('form#login_form, form[action*="login"]');
                if (form) { form.submit(); return; }
                document.querySelector("input[name='pass']").form.submit();
            }
        """)

        # Wait for redirect away from login
        try:
            await page.wait_for_url(
                lambda url: "/login" not in url and "checkpoint" not in url,
                timeout=30_000,
            )
            print("Login successful — saving session ...")
        except Exception:
            current = page.url
            await page.screenshot(path="/tmp/fb_after_login.png")
            if "checkpoint" in current or "two_step" in current:
                print(f"2FA detected: {current} — waiting up to 2 minutes ...")
                try:
                    await page.wait_for_url(
                        lambda url: "/login" not in url and "checkpoint" not in url and "two_step" not in url,
                        timeout=120_000,
                    )
                    print("2FA complete — saving session ...")
                except Exception:
                    print(f"Timed out. URL: {page.url}")
                    await browser.close()
                    sys.exit(1)
            else:
                print(f"Login failed. URL: {current}")
                print("Check /tmp/fb_after_login.png for details.")
                await browser.close()
                sys.exit(1)

        await context.storage_state(path=str(output))
        print(f"Session saved to {output_path}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
