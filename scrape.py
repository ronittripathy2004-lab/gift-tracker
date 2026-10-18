"""
Opens the Belong GIFT City funds page in a real (headless) browser, reads every
fund card for both Regular and Direct plans, and saves:
  - funds.csv        (one row per fund per plan)
  - screenshot.png   (full-page picture, as a visual backup)
"""
import csv
import re
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

URL = "https://getbelong.com/tools/gift-city-mutual-funds/"
LABELS = ["Min Invest.", "Addl. Inv.", "1W returns", "1M returns", "3M returns", "All returns"]
PLANS = ["Regular Funds", "Direct Funds"]


def parse_card(text):
    """text = visible text of one fund card, split into lines."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    row = {"fund_name": lines[0] if lines else "", "raw_text": " | ".join(lines)}
    if len(lines) > 1:
        row["category"] = lines[1]
    for label in LABELS:
        value = ""
        if label in lines:
            i = lines.index(label)
            # value is usually the line right after the label
            if i + 1 < len(lines) and lines[i + 1] not in LABELS:
                value = lines[i + 1]
            # or the line before it (if the layout is value-then-label)
            elif i > 0 and lines[i - 1] not in LABELS:
                value = lines[i - 1]
        else:
            # label and value may be on one line, e.g. "1W returns 0.5%"
            for l in lines:
                if l.startswith(label):
                    value = l[len(label):].strip()
        row[label] = value
    return row


def main():
    rows = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)  # let numbers finish loading

        for plan in PLANS:
            page.get_by_text(plan, exact=True).first.click()
            page.wait_for_timeout(2000)
            cards = page.locator('a[href*="/tools/gift-city-mutual-funds/"]')
            for i in range(cards.count()):
                card = cards.nth(i)
                href = card.get_attribute("href") or ""
                # skip footer/menu links; real cards have "returns" text
                text = card.inner_text()
                if "returns" not in text.lower():
                    continue
                row = parse_card(text)
                row["plan"] = plan.replace(" Funds", "")
                row["url"] = href
                row["fetched_at"] = stamp
                rows.append(row)
            if plan == PLANS[0]:
                page.screenshot(path="screenshot_regular.png", full_page=True)
            else:
                page.screenshot(path="screenshot_direct.png", full_page=True)

        browser.close()

    if not rows:
        raise SystemExit("No fund cards found - page layout may have changed.")

    cols = ["plan", "fund_name", "category"] + LABELS + ["url", "fetched_at", "raw_text"]
    with open("funds.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows")


if __name__ == "__main__":
    main()
