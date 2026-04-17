"""
MoomooClient — §4.8.3 full interface for real-time market data + paper/live execution.

Every return dict carries `_source: "moomoo"` so Hard Risk Gate (§10) can assert provenance.
Timestamps T0 (`ts_exchange`) and T1 (`ts_received`) are emitted per §10A.2.

Requires:
  - moomoo OpenD running at MOOMOO_HOST:MOOMOO_PORT (default 127.0.0.1:11111)
  - moomoo-api Python package installed
  - Level 2 subscription (confirmed per project memory)
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from moomoo import (
    KLType,
    Market,
    OpenQuoteContext,
    OpenSecTradeContext,
    OrderType as MooOrderType,
    RET_OK,
    SecurityFirm,
    SubType,
    TrdEnv,
    TrdMarket,
    TrdSide,
)

# ---------------------------------------------------------------------------
# Config from env (fallback to SPEC §12 defaults)
# ---------------------------------------------------------------------------
MOOMOO_HOST = os.getenv("MOOMOO_HOST", "127.0.0.1")
MOOMOO_PORT = int(os.getenv("MOOMOO_PORT", "11111"))


def _utc_now_iso() -> str:
    """UTC ISO8601 with millisecond precision, trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _to_moomoo_code(ticker: str) -> str:
    """Convert bare ticker (e.g. 'NVDA') to moomoo format (e.g. 'US.NVDA').

    If already prefixed (e.g. 'US.NVDA', 'HK.00700'), pass through.
    Default market is US (all tickers in our §3 universe are US-listed).
    """
    if "." in ticker and ticker.split(".")[0] in ("US", "HK", "SH", "SZ", "SG"):
        return ticker
    return f"US.{ticker}"


def _tag(d: dict, ts_exchange: str | None = None) -> dict:
    """Stamp _source + T0/T1 on a return dict. Mutates and returns `d`."""
    d["_source"] = "moomoo"
    d["ts_received"] = _utc_now_iso()
    if ts_exchange:
        d["ts_exchange"] = ts_exchange
        d["_ts_exchange_approximated"] = False
    else:
        # Best-effort: use ts_received as T0 approximation
        d["ts_exchange"] = d["ts_received"]
        d["_ts_exchange_approximated"] = True
    return d


class MoomooConnectionError(ConnectionError):
    """Raised when OpenD is unreachable or returns an error."""


class MoomooClient:
    """
    Thin wrapper around moomoo OpenAPI.

    Lazy: does NOT connect at __init__. Connections are opened on first call
    to each context type (quote / trade) and reused.
    """

    def __init__(
        self,
        host: str = MOOMOO_HOST,
        port: int = MOOMOO_PORT,
    ):
        self._host = host
        self._port = port
        self._quote_ctx: OpenQuoteContext | None = None
        self._trd_ctx: OpenSecTradeContext | None = None

    # ---- context lifecycle -----------------------------------------------

    def _get_quote_ctx(self) -> OpenQuoteContext:
        if self._quote_ctx is None:
            self._quote_ctx = OpenQuoteContext(host=self._host, port=self._port)
        return self._quote_ctx

    def _get_trd_ctx(self, trd_env: str = "SIMULATE") -> OpenSecTradeContext:
        if self._trd_ctx is None:
            self._trd_ctx = OpenSecTradeContext(
                filter_trdmarket=TrdMarket.NONE,
                host=self._host,
                port=self._port,
                security_firm=SecurityFirm.FUTUSECURITIES,
            )
        return self._trd_ctx

    def close(self):
        if self._quote_ctx is not None:
            self._quote_ctx.close()
            self._quote_ctx = None
        if self._trd_ctx is not None:
            self._trd_ctx.close()
            self._trd_ctx = None

    # ---- §4.8.3 interface ------------------------------------------------

    def get_realtime_quote(self, ticker: str) -> dict[str, Any]:
        """<1s latency. Uses get_market_snapshot (no subscription needed).

        Returns dict per §4.8.3:
            price, bid, ask, volume, ts_exchange (T0), ts_received (T1), _source
        """
        code = _to_moomoo_code(ticker)
        ctx = self._get_quote_ctx()
        ret, data = ctx.get_market_snapshot([code])
        if ret != RET_OK:
            raise MoomooConnectionError(f"get_market_snapshot({code}) failed: {data}")

        row = data.iloc[0]
        update_time = str(row.get("update_time", ""))
        # moomoo update_time is exchange time (local, not UTC). Best effort T0.
        result = {
            "ticker": ticker,
            "price": float(row["last_price"]),
            "bid": float(row.get("bid_price", row["last_price"])),
            "ask": float(row.get("ask_price", row["last_price"])),
            "volume": int(row["volume"]),
            "open": float(row.get("open_price", 0)),
            "high": float(row.get("high_price", 0)),
            "low": float(row.get("low_price", 0)),
            "prev_close": float(row.get("prev_close_price", 0)),
            "turnover": float(row.get("turnover", 0)),
        }
        return _tag(result, ts_exchange=update_time if update_time else None)

    def get_live_options_chain(
        self, ticker: str, expiration: str | None = None
    ) -> dict[str, Any]:
        """Live options chain with IV, OI, greeks."""
        code = _to_moomoo_code(ticker)
        ctx = self._get_quote_ctx()

        kwargs: dict[str, Any] = {}
        if expiration:
            kwargs["start"] = expiration
            kwargs["end"] = expiration

        ret, data = ctx.get_option_chain(code, **kwargs)
        if ret != RET_OK:
            raise MoomooConnectionError(f"get_option_chain({code}) failed: {data}")

        chains = []
        for _, row in data.iterrows():
            chains.append({
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "option_type": str(row.get("option_type", "")),
                "strike_price": float(row.get("strike_price", 0)),
                "expiry": str(row.get("strike_time", "")),
                "iv": float(row.get("implied_volatility", 0)) if row.get("implied_volatility") else None,
                "open_interest": int(row.get("open_interest", 0)) if row.get("open_interest") else 0,
                "last_price": float(row.get("last_price", 0)) if row.get("last_price") else None,
                "volume": int(row.get("volume", 0)) if row.get("volume") else 0,
            })

        result = {
            "ticker": ticker,
            "expiration": expiration,
            "chain_count": len(chains),
            "chains": chains,
        }
        return _tag(result)

    def get_order_book(self, ticker: str, depth: int = 10) -> dict[str, Any]:
        """Top N bid/ask levels. Requires subscription."""
        code = _to_moomoo_code(ticker)
        ctx = self._get_quote_ctx()

        # Subscribe if not already
        ctx.subscribe([code], [SubType.ORDER_BOOK])
        ret, data = ctx.get_order_book(code, num=min(depth, 10))
        if ret != RET_OK:
            raise MoomooConnectionError(f"get_order_book({code}) failed: {data}")

        result = {
            "ticker": ticker,
            "code": code,
            "Bid": data.get("Bid", []),
            "Ask": data.get("Ask", []),
        }
        return _tag(result)

    def get_session_state(self, ticker: str) -> str:
        """One of: 'pre_market' | 'regular' | 'after_hours' | 'closed'."""
        code = _to_moomoo_code(ticker)
        ctx = self._get_quote_ctx()
        ret, data = ctx.get_market_state([code])
        if ret != RET_OK:
            raise MoomooConnectionError(f"get_market_state({code}) failed: {data}")

        state_str = str(data.iloc[0].get("market_state", "CLOSED")).upper()
        mapping = {
            "MORNING": "regular",
            "AFTERNOON": "regular",
            "NIGHT_OPEN": "after_hours",
            "REST": "closed",
            "PRE_MARKET_BEGIN": "pre_market",
            "PRE_MARKET_END": "pre_market",
            "AFTER_HOURS_BEGIN": "after_hours",
            "AFTER_HOURS_END": "after_hours",
            "EARLY_CLOSED": "closed",
            "CLOSED": "closed",
        }
        return mapping.get(state_str, "closed")

    def get_historical_klines(
        self,
        ticker: str,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Historical OHLC (preferred over yfinance per §4.8.1)."""
        code = _to_moomoo_code(ticker)
        ctx = self._get_quote_ctx()

        ktype_map = {
            "1m": KLType.K_1M, "5m": KLType.K_5M, "15m": KLType.K_15M,
            "30m": KLType.K_30M, "60m": KLType.K_60M, "1d": KLType.K_DAY,
            "1w": KLType.K_WEEK, "1M": KLType.K_MON,
        }
        ktype = ktype_map.get(interval, KLType.K_DAY)

        kwargs: dict[str, Any] = {"code": code, "ktype": ktype, "max_count": 1000}
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end

        ret, data, _ = ctx.request_history_kline(**kwargs)
        if ret != RET_OK:
            raise MoomooConnectionError(f"request_history_kline({code}) failed: {data}")

        klines = []
        for _, row in data.iterrows():
            klines.append(_tag({
                "ticker": ticker,
                "time": str(row.get("time_key", "")),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "turnover": float(row.get("turnover", 0)),
            }))

        return klines

    def place_order(
        self,
        ticker: str,
        side: str,
        qty: int,
        order_type: str = "NORMAL",
        trd_env: str = "SIMULATE",
        **kwargs,
    ) -> dict[str, Any]:
        """Submit order. trd_env='SIMULATE' (paper) or 'REAL' (live).

        Returns {order_id, status, ts_submitted, _source: 'moomoo'}.
        """
        code = _to_moomoo_code(ticker)
        ctx = self._get_trd_ctx(trd_env)

        trd_env_enum = TrdEnv.SIMULATE if trd_env == "SIMULATE" else TrdEnv.REAL
        side_enum = TrdSide.BUY if side.upper() == "BUY" else TrdSide.SELL
        otype = MooOrderType.MARKET if order_type.upper() == "MARKET" else MooOrderType.NORMAL

        order_kwargs: dict[str, Any] = {
            "code": code,
            "qty": qty,
            "trd_side": side_enum,
            "order_type": otype,
            "trd_env": trd_env_enum,
        }
        if "price" in kwargs:
            order_kwargs["price"] = float(kwargs["price"])
        elif otype == MooOrderType.NORMAL:
            # Need a price for limit orders — get current price
            quote = self.get_realtime_quote(ticker)
            order_kwargs["price"] = quote["price"]

        if "acc_id" in kwargs:
            order_kwargs["acc_id"] = kwargs["acc_id"]

        ret, data = ctx.place_order(**order_kwargs)
        if ret != RET_OK:
            raise MoomooConnectionError(f"place_order({code}) failed: {data}")

        row = data.iloc[0]
        result = {
            "ticker": ticker,
            "order_id": str(row.get("order_id", "")),
            "status": str(row.get("order_status", "")),
            "ts_submitted": _utc_now_iso(),
        }
        return _tag(result)

    def wait_for_fill(
        self, order_id: str, timeout_sec: int = 10, trd_env: str = "SIMULATE"
    ) -> dict[str, Any]:
        """Block until order filled/rejected/timeout.

        Returns {status, fill_price, fill_qty, ts_filled, _source}.
        """
        ctx = self._get_trd_ctx(trd_env)
        trd_env_enum = TrdEnv.SIMULATE if trd_env == "SIMULATE" else TrdEnv.REAL

        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            ret, data = ctx.order_list_query(
                order_id=order_id, trd_env=trd_env_enum, refresh_cache=True
            )
            if ret != RET_OK:
                raise MoomooConnectionError(f"order_list_query failed: {data}")

            if data.empty:
                time.sleep(0.5)
                continue

            row = data.iloc[0]
            status = str(row.get("order_status", "")).upper()

            if "FILLED" in status:
                result = {
                    "order_id": order_id,
                    "status": "filled" if "ALL" in status else "partial",
                    "fill_price": float(row.get("dealt_avg_price", 0)),
                    "fill_qty": int(row.get("dealt_qty", 0)),
                    "ts_filled": _utc_now_iso(),
                }
                return _tag(result)

            if any(s in status for s in ("CANCEL", "REJECT", "FAILED", "DELETED")):
                result = {
                    "order_id": order_id,
                    "status": "rejected",
                    "fill_price": None,
                    "fill_qty": 0,
                    "ts_filled": None,
                }
                return _tag(result)

            time.sleep(0.5)

        # Timeout — do NOT retry per §10A.4
        result = {
            "order_id": order_id,
            "status": "timeout",
            "fill_price": None,
            "fill_qty": 0,
            "ts_filled": None,
        }
        return _tag(result)
