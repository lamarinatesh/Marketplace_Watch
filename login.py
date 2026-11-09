"""One-time: open a real browser window, log in to the Facebook account the bot will use.

The session is saved into ./user-data so the bot stays logged in on every run.
Run this again only if the bot later says it got bounced to the login page.
"""
import yaml
from playwright.sync_api import sync_playwright


def main():
    with open("config.yml") as f:
        cfg = yaml.safe_load(f)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            cfg["user_data_dir"], headless=False, viewport={"width": 1280, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.facebook.com/login")

        print("\n" + "=" * 68)
        print("  Log in to the Facebook account the bot will use in the browser window.")
        print("  Solve any security checkpoint until you can see your feed.")
        print("=" * 68)
        input("\n  ↳ When you're logged in and see your feed, press Enter here... ")

        ctx.close()
        print("  ✓ Session saved to ./user-data — you can close this and run the bot.\n")


if __name__ == "__main__":
    main()
