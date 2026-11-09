"""Open the (logged-in) Marketplace results page and pull the listing cards."""
from playwright.sync_api import sync_playwright

# Runs inside the page. Every listing on a results page is an <a> pointing at
# /marketplace/item/<id>/. We grab the id, the card's text, and its thumbnail.
_EXTRACT_JS = r"""
() => {
  const seen = {};
  const out = [];
  const anchors = document.querySelectorAll('a[href*="/marketplace/item/"]');
  for (const a of anchors) {
    const href = a.getAttribute('href') || '';
    const key = '/marketplace/item/';
    const idx = href.indexOf(key);
    if (idx === -1) continue;
    let id = href.slice(idx + key.length).split('/')[0].split('?')[0];
    if (!id || seen[id]) continue;
    if (!/^[0-9]+$/.test(id)) continue;
    seen[id] = true;
    const img = a.querySelector('img');
    out.push({
      id: id,
      url: 'https://www.facebook.com/marketplace/item/' + id + '/',
      raw_text: (a.innerText || '').trim(),
      image: img ? img.src : null,
      img_alt: img ? (img.getAttribute('alt') || '') : ''
    });
  }
  return out;
}
"""


def scrape(cfg: dict) -> list[dict]:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            cfg["user_data_dir"],
            headless=cfg.get("headless", True),
            viewport={"width": 1280, "height": 900},
            args=[
                # Use Chromium's basic cookie store instead of the macOS Keychain,
                # which otherwise stalls invisibly under launchd (no UI to approve
                # the Keychain-access prompt).
                "--password-store=basic",
            ],
            timeout=60000,  # fail fast instead of hanging forever
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        urls = cfg.get("marketplace_urls") or (
            [cfg["marketplace_url"]] if cfg.get("marketplace_url") else []
        )
        found = {}
        try:
            for url in urls:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4000)

                if "/login" in page.url or "login.php" in page.url:
                    raise RuntimeError(
                        "Facebook bounced us to the login page — run:  python login.py"
                    )

                # Results are lazy-loaded; scroll to pull in more cards.
                for _ in range(cfg.get("scroll_passes", 4)):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(1500)

                for it in page.evaluate(_EXTRACT_JS):
                    found[it["id"]] = it  # de-dupe across searches by listing id
            return list(found.values())
        finally:
            ctx.close()
