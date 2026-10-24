import csv, os, sys, time
from datetime import datetime, timezone
import requests

URL = "https://api2.bybit.com/fiat/otc/item/online"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.bybit.com",
    "Referer": "https://www.bybit.com/",
}
PAGE_SIZE = 20
TARGET = 300
# Bybit's side flag: "1" = ads you BUY USDT from, "0" = ads you SELL USDT to.
# Verify on first run: "buy" prices should be the lowest, "sell" the highest.
SIDES = {"buy": "1", "sell": "0"}

FIELDS = ["snapshot_utc", "side", "rank", "ad_id", "nickname", "price",
          "available_qty", "min_amount", "max_amount", "payments",
          "recent_orders", "recent_exec_rate", "is_online", "auth_status"]


def fetch_page(side, page, retries=4):
    body = {"userId": "", "tokenId": "USDT", "currencyId": "NGN", "payment": [],
            "side": side, "size": str(PAGE_SIZE), "page": str(page),
            "amount": "", "authMaker": False, "canTrade": False}
    for attempt in range(retries):
        try:
            r = requests.post(URL, json=body, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if data.get("ret_code") not in (0, None):
                raise ValueError(f"API error: {data}")
            return data["result"]["items"] or []
        except Exception as e:
            print(f"[{side} p{page}] attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return None


def fetch_side(side_name, side_code, ts):
    rows, page = [], 1
    while len(rows) < TARGET:
        items = fetch_page(side_code, page)
        if items is None:
            raise RuntimeError(f"Failed fetching {side_name} page {page}")
        if not items:
            break
        for it in items:
            rows.append({
                "snapshot_utc": ts, "side": side_name, "rank": len(rows) + 1,
                "ad_id": it.get("id"), "nickname": it.get("nickName"),
                "price": float(it.get("price", 0)),
                "available_qty": it.get("lastQuantity"),
                "min_amount": it.get("minAmount"), "max_amount": it.get("maxAmount"),
                "payments": "|".join(map(str, it.get("payments", []))),
                "recent_orders": it.get("recentOrderNum"),
                "recent_exec_rate": it.get("recentExecuteRate"),
                "is_online": it.get("isOnline"), "auth_status": it.get("authStatus"),
            })
            if len(rows) >= TARGET:
                break
        page += 1
        time.sleep(0.7)  # be polite
    return rows


def main():
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for name, code in SIDES.items():
        rows += fetch_side(name, code, ts)

    os.makedirs("data", exist_ok=True)
    path = f"data/bybit_usdt_ngn_{now:%Y-%m}.csv"
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
