# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prices

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{str(info)[:300]}]"), flush=True)
    ok, fail = ok + bool(cond), fail + (not cond)


calls = []
def fake(url, body=None):
    calls.append((url, body))
    if "coingecko" in url:
        return {"bitcoin": {"usd": 91234.5, "usd_24h_change": -1.5}, "ethereum": {"usd": 3100.25, "usd_24h_change": 2.0},
                "pax-gold": {"usd": 2650.0}, "solana": {"usd": "bad"}}
    if "mempool.space" in url:
        return {"chain_stats": {"funded_txo_sum": 150_000_000, "spent_txo_sum": 50_000_000, "tx_count": 7},
                "mempool_stats": {"funded_txo_sum": 1000, "spent_txo_sum": 0}}
    if "publicnode" in url:
        return {"jsonrpc": "2.0", "id": 1, "result": hex(2_500_000_000_000_000_000)}
    raise ValueError("unexpected url")


P = prices.Prices(fake)
q = P.quotes(["btc", "ETH", "XAUB", "SOL", "MOON", "../x"])
check("quotes: known coins priced, made-up ones (MOON) and junk ignored", set(q["quotes"]) == {"BTC", "ETH", "XAUB"}, q)
check("quotes: price + 24 h change as a fraction", q["quotes"]["BTC"] == {"p": 91234.5, "chg24": -0.015} and q["quotes"]["XAUB"]["chg24"] is None)
check("quotes: one request, only the coin ids asked for", len(calls) == 1 and "ids=bitcoin,ethereum,pax-gold,solana&" in calls[0][0], calls)
q2 = P.quotes(["ETH", "BTC", "SOL", "XAUB"])
check("quotes: second ask within 60 s comes from the cache", len(calls) == 1 and q2.get("cached") is True, calls)
w = P.wallet("btc", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
check("btc wallet: confirmed balance + unconfirmed", w.get("balance") == 1.0 and w.get("pending") == 0.00001 and w.get("txs") == 7, w)
w = P.wallet("eth", "0x" + "ab" * 20)
check("eth wallet: balance from eth_getBalance", w.get("balance") == 2.5 and calls[-1][1]["method"] == "eth_getBalance", w)
n = len(calls)
for chain, bad in (("btc", "bc1/../../x"), ("btc", "notanaddress"), ("eth", "0x123"), ("eth", "0x" + "zz" * 20), ("doge", "D123"),
                   ("btc", "1" * 60), ("eth", "0x" + "ab" * 20 + "?x=1")):
    check(f"bad address refused before anything is sent: {chain} {bad[:20]!r}", "error" in P.wallet(chain, bad))
check("no request was made for any bad address", len(calls) == n, calls[n:])
for url in ("https://evil.example/x", "http://api.coingecko.com/api/v3/simple/price", "file:///C:/x"):
    try:
        prices.Prices._http(url); bad = False
    except ValueError:
        bad = True
    check(f"only the fixed services over https: {url}", bad)


def broken(url, body=None):
    raise OSError("no network")
check("service down: a plain error, nothing cached", "error" in prices.Prices(broken).quotes(["BTC"]))


class FakeTabs:
    def __init__(self, metas): self.metas = metas
    def _meta(self, tab_id):
        if tab_id not in self.metas: raise ValueError("no tab")
        return self.metas[tab_id]

import app
api = app.Api.__new__(app.Api)
api._tabs = lambda: FakeTabs({"plain": {}, "mint": {"prices": True}, "str": {"prices": "true"}})
api._prices = prices.Prices(fake)
check("plain tab refused", "error" in api.price_call("plain", "quotes"))
check("prices as text refused", "error" in api.price_call("str", "quotes"))
check("unknown op (an order) refused", "error" in api.price_call("mint", "order", {"side": "buy"}))
check("Mintworks tab gets quotes", "BTC" in api.price_call("mint", "quotes", {"symbols": ["BTC"]}).get("quotes", {}))
check("Mintworks tab gets a wallet", api.price_call("mint", "wallet", {"chain": "eth", "address": "0x" + "ab" * 20}).get("balance") == 2.5)
import json
mpath = os.path.join(app.HERE, "data", "tabs", "10deedaefc", "meta.json")
if os.path.exists(mpath):
    meta = json.load(open(mpath, encoding="utf-8"))
    check("Mintworks meta has prices: true and no other new power", meta.get("prices") is True and not any(meta.get(k) for k in ("vm", "studio", "online", "osdesign")))
else:
    print("SKIP Mintworks meta check: the Mintworks tab is not installed in this copy")

if "live" in sys.argv:
    L = prices.Prices()
    q = L.quotes(["BTC", "ETH", "XAUB", "USDC"])
    qs = q.get("quotes", {})
    check("LIVE: CoinGecko answers with real prices", qs.get("BTC", {}).get("p", 0) > 1000 and qs.get("ETH", {}).get("p", 0) > 100
          and 0.9 < qs.get("USDC", {}).get("p", 0) < 1.1, q)
    print("  live sample:", {k: v["p"] for k, v in qs.items()})
    w = L.wallet("btc", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    check("LIVE: mempool.space answers a Bitcoin address", isinstance(w.get("balance"), float) and w.get("txs", 0) > 0, w)
    w = L.wallet("eth", "0x00000000219ab540356cBB839Cbe05303d7705Fa")
    check("LIVE: publicnode answers an Ether address", isinstance(w.get("balance"), float) and w["balance"] > 1000, w)

print(f"{ok}/{ok + fail} passed")
sys.exit(1 if fail else 0)
