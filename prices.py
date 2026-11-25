# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, re, threading, time, urllib.error, urllib.request

COINS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple", "ADA": "cardano", "AVAX": "avalanche-2",
         "LINK": "chainlink", "DOT": "polkadot", "LTC": "litecoin", "TON": "the-open-network", "DOGE": "dogecoin",
         "USDC": "usd-coin", "USDT": "tether", "DAI": "dai", "XAUB": "pax-gold"}
QUOTE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=usd&include_24hr_change=true"
BTC_URL = "https://mempool.space/api/address/%s"
ETH_RPC = "https://ethereum-rpc.publicnode.com"
HOSTS = ("api.coingecko.com", "mempool.space", "ethereum-rpc.publicnode.com")
BTC_ADDR = re.compile(r"^(bc1[02-9ac-hj-np-z]{11,87}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$")
ETH_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
UA = "RandisUDS-prices/1 (read-only)"


class Prices:
    def __init__(self, fetch=None):
        self._fetch = fetch or self._http
        self._cache = {}
        self._lock = threading.Lock()

    @staticmethod
    def _http(url, body=None):
        host = url.split("/")[2]
        if host not in HOSTS or not url.startswith("https://"):
            raise ValueError("not an allowed price service")
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"User-Agent": UA, "Accept": "application/json",
                                              **({"Content-Type": "application/json"} if body is not None else {})})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read(1_000_000).decode("utf-8"))

    def _cached(self, key, ttl, make):
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.time() - hit[0] < ttl:
                return dict(hit[1], cached=True)
        out = make()
        if "error" not in out:
            with self._lock:
                self._cache[key] = (time.time(), out)
        return out

    def quotes(self, symbols):
        syms = sorted({str(s).upper() for s in (symbols or []) if str(s).upper() in COINS}) or sorted(COINS)
        def make():
            try:
                data = self._fetch(QUOTE_URL % ",".join(sorted({COINS[s] for s in syms})))
            except (OSError, ValueError, urllib.error.URLError) as e:
                return {"error": f"The price service didn't answer: {e}"}
            out = {}
            for s in syms:
                d = data.get(COINS[s]) if isinstance(data, dict) else None
                if isinstance(d, dict) and isinstance(d.get("usd"), (int, float)) and d["usd"] > 0:
                    ch = d.get("usd_24h_change")
                    out[s] = {"p": float(d["usd"]), "chg24": float(ch) / 100 if isinstance(ch, (int, float)) else None}
            return {"quotes": out, "t": time.time(), "source": "CoinGecko (public, no key)"}
        return self._cached(("q",) + tuple(syms), 60, make)

    def wallet(self, chain, address):
        chain, address = str(chain or "").lower(), str(address or "").strip()
        if chain == "btc" and BTC_ADDR.match(address):
            def make():
                try:
                    d = self._fetch(BTC_URL % address)
                    c, m = d.get("chain_stats", {}), d.get("mempool_stats", {})
                    sat = c["funded_txo_sum"] - c["spent_txo_sum"]
                    pend = m.get("funded_txo_sum", 0) - m.get("spent_txo_sum", 0)
                except (OSError, ValueError, KeyError, TypeError, AttributeError, urllib.error.URLError) as e:
                    return {"error": f"The Bitcoin lookup didn't work: {e}"}
                return {"chain": "btc", "address": address, "balance": sat / 1e8, "pending": pend / 1e8, "unit": "BTC",
                        "txs": c.get("tx_count"), "t": time.time(), "source": "mempool.space (public, no key)"}
        elif chain == "eth" and ETH_ADDR.match(address):
            def make():
                try:
                    d = self._fetch(ETH_RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]})
                    wei = int(d["result"], 16)
                except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as e:
                    return {"error": f"The Ether lookup didn't work: {e}"}
                return {"chain": "eth", "address": address, "balance": wei / 1e18, "unit": "ETH", "t": time.time(),
                        "source": "publicnode (public, no key)"}
        else:
            return {"error": "Give a Bitcoin address (bc1..., 1..., 3...) or an Ether address (0x + 40 hex)."}
        return self._cached(("w", chain, address), 120, make)
