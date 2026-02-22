#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone

READ_ONLY = True


def out(obj):
    print(json.dumps(obj, separators=(",", ":"), default=str))


def status_cmd():
    try:
        import robin_stocks.robinhood as rh  # noqa: F401
        installed = True
        msg = "robin_stocks available"
    except Exception as e:
        installed = False
        msg = f"robin_stocks import failed: {e}"

    out({
        "ok": installed,
        "read_only": READ_ONLY,
        "python": sys.version.split()[0],
        "robin_stocks_installed": installed,
        "message": msg,
    })


def _safe_float(v):
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def _normalize_order(o):
    return {
        "order_id": o.get("id") or o.get("order_id") or "",
        "symbol": o.get("symbol") or "",
        "side": o.get("side") or "unknown",
        "order_type": o.get("type") or "unknown",
        "time_in_force": o.get("time_in_force") or "unknown",
        "status": o.get("state") or o.get("status") or "unknown",
        "quantity": _safe_float(o.get("quantity")),
        "filled_quantity": _safe_float(o.get("cumulative_quantity") or o.get("filled_quantity")),
        "limit_price": _safe_float(o.get("price")) if o.get("price") not in (None, "") else None,
        "avg_fill_price": _safe_float(o.get("average_price")) if o.get("average_price") not in (None, "") else None,
        "submitted_at": o.get("created_at"),
        "updated_at": o.get("updated_at") or o.get("last_transaction_at"),
        "raw": o,
    }


def _normalize_holding(h):
    return {
        "symbol": h.get("symbol") or h.get("instrument") or "",
        "quantity": _safe_float(h.get("quantity") or h.get("shares_held_for_buys") or h.get("shares_available_for_exercise")),
        "average_buy_price": _safe_float(h.get("average_buy_price")) if h.get("average_buy_price") not in (None, "") else None,
        "raw": h,
    }


def _login():
    import robin_stocks.robinhood as rh

    username = os.getenv("RH_USERNAME")
    password = os.getenv("RH_PASSWORD")
    mfa_code = os.getenv("RH_MFA_CODE")

    if not username or not password:
        raise RuntimeError("missing RH_USERNAME/RH_PASSWORD env vars")

    # read-only policy: login + GET calls only in this script
    rh.login(username=username, password=password, mfa_code=mfa_code, store_session=False)
    return rh


def holdings_cmd():
    rh = _login()
    data = rh.build_holdings(with_dividends=False)

    # build_holdings may return dict keyed by symbol
    holdings = []
    if isinstance(data, dict):
        for symbol, payload in data.items():
            obj = dict(payload)
            obj.setdefault("symbol", symbol)
            holdings.append(_normalize_holding(obj))

    out({"read_only": True, "holdings": holdings, "orders": []})


def orders_cmd(since=None):
    rh = _login()
    raw = rh.get_all_stock_orders() or []

    orders = []
    for item in raw:
        n = _normalize_order(item)
        if since and n.get("submitted_at"):
            try:
                ts = datetime.fromisoformat(n["submitted_at"].replace("Z", "+00:00"))
                s = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
                if ts < s:
                    continue
            except Exception:
                pass
        orders.append(n)

    out({"read_only": True, "holdings": [], "orders": orders})


def sync_cmd(since=None):
    rh = _login()

    h_data = rh.build_holdings(with_dividends=False)
    holdings = []
    if isinstance(h_data, dict):
        for symbol, payload in h_data.items():
            obj = dict(payload)
            obj.setdefault("symbol", symbol)
            holdings.append(_normalize_holding(obj))

    raw_orders = rh.get_all_stock_orders() or []
    orders = []
    for item in raw_orders:
        n = _normalize_order(item)
        if since and n.get("submitted_at"):
            try:
                ts = datetime.fromisoformat(n["submitted_at"].replace("Z", "+00:00"))
                s = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
                if ts < s:
                    continue
            except Exception:
                pass
        orders.append(n)

    out({"read_only": True, "holdings": holdings, "orders": orders})


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("status")
    sp.add_parser("holdings")

    o = sp.add_parser("orders")
    o.add_argument("--since", default=None)

    s = sp.add_parser("sync")
    s.add_argument("--since", default=None)

    args = p.parse_args()

    try:
        if args.cmd == "status":
            status_cmd()
        elif args.cmd == "holdings":
            holdings_cmd()
        elif args.cmd == "orders":
            orders_cmd(args.since)
        elif args.cmd == "sync":
            sync_cmd(args.since)
        else:
            raise RuntimeError("unknown command")
    except Exception as e:
        out({
            "read_only": True,
            "error": str(e),
            "holdings": [],
            "orders": [],
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
