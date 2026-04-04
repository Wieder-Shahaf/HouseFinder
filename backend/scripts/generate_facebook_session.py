#!/usr/bin/env python3
"""One-time manual login script to generate a Facebook session file.

Usage:
    python scripts/generate_facebook_session.py [output_path]

Default output: /data/facebook_session.json

Opens a visible Chromium browser window. The user must:
1. Log in to Facebook manually
2. Press Enter in the terminal when done

The script saves Playwright storage_state (cookies + localStorage) to the output path.
Both facebook_groups.py and facebook_marketplace.py load this file at runtime.
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


DEFAULT_OUTPUT = "/data/facebook_session.json"


async def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Session will be saved to: {output_path}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="he-IL",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        await page.goto("https://www.facebook.com/login/")

        print("=" * 60)
        print("A browser window has opened.")
        print("Log in to your Facebook account manually.")
        print("When you see your Facebook home feed, come back here")
        print("and press Enter to save the session.")
        print("=" * 60)

        input("\nPress Enter when logged in... ")

        await context.storage_state(path=str(output))
        print(f"\nSession saved to {output_path}")
        print("Both Facebook scrapers will use this session file.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
