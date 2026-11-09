"""Set the bot account's Marketplace location + radius (one-time).

Facebook ties the Marketplace feed to the account's saved location — it cannot be
forced through the URL. This opens the bot's own logged-in browser on the Free
listings page so you can set location + radius once; it then sticks for every run.
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
        page.goto("https://www.facebook.com/marketplace/category/free")

        print("\n" + "=" * 70)
        print("  Set your Marketplace location + radius in the browser window:")
        print("    1. Click the location control near the top-left (shows a city).")
        print("    2. Search for your city (e.g. 'Austin, TX') and select it.")
        print("    3. Drag the Radius slider to your preferred distance.")
        print("    4. Click Apply — the listings should refresh to your area.")
        print("=" * 70)
        input("\n  ↳ Once the listings have refreshed, press Enter here to save... ")

        ctx.close()
        print("  ✓ Location saved to the account. "
              "Next:  .venv/bin/python bot.py --dry-run\n")


if __name__ == "__main__":
    main()
