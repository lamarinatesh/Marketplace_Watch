#!/usr/bin/env python3
"""Marketplace listings watcher: scrape -> filter -> dedup -> alert.

Usage:
    python bot.py                 # one scan (what the scheduler runs)
    python bot.py --loop          # run forever, scanning every interval_minutes
    python bot.py --dry-run       # scan + filter, print matches, NO alerts, NO dedup writes
    python bot.py --backfill      # alert on ALL current matches (skip first-run baselining)
    python bot.py --test-telegram # send a test message to confirm Telegram works
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

import notifier
from scraper import scrape
from store import Store

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / ".bot.lock"

_PRICE_RE = re.compile(r"free|\$\s?[\d,]+", re.I)


def load_config() -> dict:
    with open(ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def parse_item(it: dict) -> dict:
    """Turn a raw card into {title, price, location} using best-effort heuristics."""
    lines = [ln.strip() for ln in (it.get("raw_text") or "").split("\n") if ln.strip()]
    title = ""
    price = ""
    location = lines[-1] if lines else ""

    # Cards read like: ["Just listed", "Free", "<title>", "<City, ST>"].
    # The line right after the price is the cleanest title.
    for i, ln in enumerate(lines):
        if _PRICE_RE.search(ln):
            price = ln
            if i + 1 < len(lines):
                title = lines[i + 1]
            break
    if not title:  # fall back to Facebook's image-alt ("<title> in <City, ST>")
        title = (it.get("img_alt") or "").strip()
    if not title and lines:
        title = lines[0]

    return {**it, "title": title, "price": price, "location": location}


def _has_word(keyword: str, text: str) -> bool:
    """Whole-word, case-insensitive match, tolerant of a plural 's'/'es'.
    Precise: 'car' drops "free car" but not "cardboard"/"cart"; 'book' drops
    "books" but spares "bookshelf"; 'couch' also catches "couches"."""
    return re.search(r"\b" + re.escape(keyword) + r"(?:es|s)?\b", text) is not None


# A price/sale signal in the TITLE means it isn't really free, even when the
# price field reads Free/$0 — a common way non-free posts sneak through.
_PRICED_RE = re.compile(r"\$\s?\d|\bobo\b|\basking\b|\bfor sale\b|\bfirm\b|\bprice\b", re.I)

# Heuristic Spanish detector: diacritics/inverted punctuation, a strong giveaway
# word, or two-plus common Spanish words.
_SPANISH_CHARS = re.compile(r"[ñáéíóúü¿¡]", re.I)
_SPANISH_STRONG = {
    "gratis", "muebles", "mueble", "vendo", "vende", "venta", "ventas", "por",
    "envío", "envio", "domicilio", "pregunta", "regalo", "ropa", "cosas", "cosa",
    "para", "del", "cama", "camas", "silla", "sillas", "sillon", "sillón",
    "niños", "ninos", "niño", "nino", "niña", "nina", "mecanico", "mecánico",
    "movil", "móvil", "futbol", "fútbol", "pescado", "comida", "hierba",
    "perfume", "perfumes", "servicio", "servicios", "herramientas", "zapatos",
    "juguetes", "juguete", "cocina", "recamara", "recámara", "colchon", "colchón",
    "escritorio", "librero", "lavadora", "secadora", "refrigerador", "congelador",
    "dueño", "dueno", "barato", "economico", "económico", "oferta", "ofertas",
    "mudanza", "disponible", "disponibles", "usado", "usada", "nuevo", "nueva",
    "precio", "precios", "mensaje", "llame", "llamar", "español", "espanol",
    "madera", "bonito", "bonita", "hermoso", "hermosa", "pequeño", "pequeno",
    "interesado", "tengo", "hola", "buenas",
}
_SPANISH_COMMON = {
    "de", "la", "el", "los", "las", "y", "un", "una", "uno", "unas", "unos",
    "con", "sin", "casa", "mesa", "todo", "todos", "grande", "cada", "es",
    "muy", "mas", "más", "sus", "tu", "mi",
}


def _looks_spanish(text: str) -> bool:
    if _SPANISH_CHARS.search(text):
        return True
    words = re.findall(r"[a-zñáéíóúü]+", text.lower())
    if any(w in _SPANISH_STRONG for w in words):
        return True
    return sum(1 for w in words if w in _SPANISH_COMMON) >= 2


def keep(item: dict, cfg: dict) -> bool:
    title = (item.get("title") or "").lower()
    price = (item.get("price") or "").lower()

    if cfg.get("require_free"):
        # Provably free: the price field literally says "free" AND the title
        # carries no price/sale signal. Fails safe — drops "$0"-but-not-free spam.
        if "free" not in price.replace(" ", ""):
            return False
        if _PRICED_RE.search(title):
            return False

    if cfg.get("exclude_spanish") and _looks_spanish(title):
        return False

    includes = [k.lower() for k in (cfg.get("include_keywords") or [])]
    excludes = [k.lower() for k in (cfg.get("exclude_keywords") or [])]
    # Both lists use precise whole-word matching (+ plurals), so "bat" matches
    # "bat"/"bats" but never "bath"/"battery"/"combat".
    if includes and not any(_has_word(k, title) for k in includes):
        return False
    if any(_has_word(k, title) for k in excludes):
        return False
    return True


def run_once(cfg: dict, dry: bool = False, backfill: bool = False) -> None:
    raw = scrape(cfg)
    matched = [it for it in map(parse_item, raw) if keep(it, cfg)]
    store = Store(str(ROOT / cfg["db_path"]))

    # First ever run: baseline everything currently listed so you don't get
    # spammed with dozens of pre-existing items. Only NEW ones alert afterwards.
    if store.is_empty() and not backfill and not dry:
        for it in matched:
            store.mark_seen(it)
        notifier.send_text(
            f"⚾ Marketplace watcher started. Baselined {len(matched)} current "
            "matching listings — you'll only be pinged about NEW ones from now on."
        )
        print(f"scraped={len(raw)} matched={len(matched)} baselined={len(matched)}")
        return

    new = [it for it in matched if not store.is_seen(it["id"])]
    print(f"scraped={len(raw)} matched={len(matched)} new={len(new)}")

    for it in new:
        if dry:
            print(f"  NEW  {it['price']:<8} {it['title']!r}  {it['url']}")
            print(f"       raw={it['raw_text']!r}")
            continue
        ok = notifier.send_listing(it)
        store.mark_seen(it)
        print(f"  {'sent' if ok else 'FAIL'}  {it['title']!r}")
        time.sleep(1)  # be gentle with Telegram

    if dry and not new:
        print("  (dry-run) sample of matched cards for tuning:")
        for it in matched[:8]:
            print(f"    {it['price']:<8} {it['title']!r}")


def acquire_lock() -> bool:
    """Stop overlapping runs from opening two browsers on the same profile."""
    if LOCK.exists() and (time.time() - LOCK.stat().st_mtime) < 25 * 60:
        print("another run looks active (.bot.lock) — skipping")
        return False
    LOCK.write_text(str(os.getpid()))
    return True


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--test-telegram", action="store_true")
    args = ap.parse_args()

    if args.test_telegram:
        ok = notifier.send_text("🤖 Test from your Marketplace bot — wiring works!")
        print("Telegram OK" if ok else "Telegram FAILED — check your token/chat id")
        sys.exit(0 if ok else 1)

    cfg = load_config()

    if args.loop:
        interval = cfg.get("interval_minutes", 30) * 60
        print(f"Looping every {cfg.get('interval_minutes', 30)} min. Ctrl-C to stop.")
        while True:
            try:
                if acquire_lock():
                    run_once(cfg, dry=args.dry_run, backfill=args.backfill)
            except Exception as e:  # noqa: BLE001
                print(f"run error: {e}")
            finally:
                LOCK.unlink(missing_ok=True)
            time.sleep(interval)
    else:
        if not acquire_lock():
            sys.exit(0)
        try:
            run_once(cfg, dry=args.dry_run, backfill=args.backfill)
        finally:
            LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
