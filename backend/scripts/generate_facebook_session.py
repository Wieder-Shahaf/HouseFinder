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

        # Dismiss cookie consent dialog — try JS across main frame + all iframes
        dismissed = False
        dismiss_js = """
            () => {
                const keywords = ['לאפשר', 'Allow all', 'Accept all', 'Accept'];
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                const btn = buttons.find(b => keywords.some(k => b.textContent.includes(k)));
                if (btn) { btn.click(); return true; }
                return false;
            }
        """
        try:
            dismissed = await page.evaluate(dismiss_js)
            if not dismissed:
                for frame in page.frames:
                    try:
                        dismissed = await frame.evaluate(dismiss_js)
                        if dismissed:
                            break
                    except Exception:
                        continue
        except Exception as e:
            print(f"Cookie dismiss JS error: {e}")

        if dismissed:
            print("Cookie dialog dismissed.")
            await page.wait_for_timeout(1_500)
        else:
            # Fallback: click the blue accept button by coordinates (bottom-left of dialog)
            print("Trying coordinate click to dismiss cookie dialog ...")
            try:
                await page.mouse.click(465, 641)
                await page.wait_for_timeout(1_500)
                print("Coordinate click done.")
            except Exception as e:
                print(f"Coordinate click failed: {e}")

        await page.screenshot(path="/tmp/fb_login_page.png")
        print("Screenshot saved to /tmp/fb_login_page.png")

        # Try multiple selectors — Facebook changes its DOM occasionally
        email_sel = "input[name='email'], #email, input[type='email']"
        pass_sel = "input[name='pass'], #pass, input[type='password']"

        await page.wait_for_selector(email_sel, timeout=15_000)
        await page.fill(email_sel, email)
        await page.fill(pass_sel, password)

        # Submit via JS to bypass any overlaying cookie dialog
        submitted = await page.evaluate("""
            () => {
                const form = document.querySelector('form#login_form, form[action*="login"]');
                if (form) { form.submit(); return true; }
                const btn = document.querySelector('button[name="login"], #loginbutton, button[type="submit"]');
                if (btn) { btn.click(); return true; }
                return false;
            }
        """)
        if not submitted:
            # Last resort: press Enter on the password field
            await page.focus(pass_sel)
            await page.keyboard.press("Enter")

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
