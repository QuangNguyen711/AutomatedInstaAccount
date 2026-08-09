"""One-time interactive Google login to capture a Playwright/Patchright storage_state.

Without a signed-in session, Google serves a stripped "limited view" of Maps to
automated/headless-looking browsers — no reviews, restricted photos. Run this once
(re-run whenever the saved session expires or is signed out), then point
GOOGLE_AUTH_STATE_PATH at the output file.

Usage: uv run python scripts/google_login_setup.py
"""

from __future__ import annotations

import asyncio
import getpass
import os

from patchright.async_api import async_playwright

STATE_PATH = ".secrets/google_auth_state.json"


async def main() -> None:
    email = input("Google email: ").strip()
    password = getpass.getpass("Google password: ")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(locale="en-US")
        page = await context.new_page()

        await page.goto("https://accounts.google.com/signin/v2/identifier?hl=en")
        await page.wait_for_timeout(2000)

        await page.get_by_label("Email or phone").fill(email)
        await page.get_by_role("button", name="Next").click()
        await page.wait_for_timeout(3000)

        await page.get_by_label("Enter your password").fill(password)
        await page.get_by_role("button", name="Next").click()

        print(
            "Submitted credentials. Waiting up to 90s — solve any captcha / "
            "'confirm it's you' prompt in the browser window if one appears..."
        )
        try:
            await page.wait_for_url("https://myaccount.google.com/**", timeout=90_000)
            print("Logged in.")
        except Exception:
            print(f"Didn't auto-detect success, current URL: {page.url}")
            print("Waiting another 30s in case you're mid-prompt...")
            await page.wait_for_timeout(30_000)

        # IMPORTANT: the account's UI language must be English for this project's ARIA-text
        # matching (rating/address/reviews-tab selectors) to work — Maps follows the signed-in
        # account's language preference, not the browser context locale. Set it once at
        # https://myaccount.google.com/language if this account defaults to something else.
        await page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        await context.storage_state(path=STATE_PATH)
        print(f"Saved auth state to {STATE_PATH}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
