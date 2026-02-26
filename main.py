# main.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from binance.client import Client

from config import BINANCE_API_KEY,BINANCE_API_SECRET
from data_loader import load_predictions_json
from market_data import get_momentums
from scoring import score_prediction
from ranking import add_selection_flags, get_selected


# =========================
# CONFIG (NO SECRETS HERE)
# =========================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

PREDICTIONS_FILE = "predictions.json"  # set to None to use demo list

# Filters / selection
CRYPTO_ONLY = False
MIN_USER_CONFIDENCE = 0.70
TOP_PCT = 0.30

# ✅ Rank by the new final score (includes entry_quality)
SCORE_COL = "final_reliability_score"

# Gates (set None to disable)
MIN_STRUCTURAL = 0.55
MIN_SCORE = None  # don't hard-gate final score by default


def _is_crypto_asset(asset: str) -> bool:
    a = (asset or "").upper().strip()
    return a in ("BTC", "ETH", "SOL") or a.endswith("USDT")


def _jsonify_cell(x: Any) -> Any:
    """Turn dict/list cells into JSON strings so CSV stays clean."""
    if isinstance(x, (dict, list)):
        return json.dumps(x, ensure_ascii=False)
    return x


def main() -> None:
    # Binance client is only required for crypto
    binance_client = None
    if BINANCE_API_KEY and BINANCE_API_SECRET:
        binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

    # -------------------------
    # 1) Load predictions
    # -------------------------
    if PREDICTIONS_FILE and Path(PREDICTIONS_FILE).exists():
        preds: List[Dict[str, Any]] = load_predictions_json(PREDICTIONS_FILE)
    else:
        # fallback demo list
        preds = [
            {
                "user_id": "U1001",
                "submission_id": "9c1f1e6e-0a1b-4e5c-9f32-1c9b7a1e0011",
                "timestamp": "2026-01-23T08:00:00Z",
                "asset": "BTCUSDT",
                "direction": "BUY",
                "confidence": 0.72,
                "horizon_hours": 4,
                "entry_price": 64000,
                "move_pct": 0.004,  # 0.4%
            },
            {
                "user_id": "U1002",
                "submission_id": "b7a29c42-7c33-4d6e-b7d1-2f81e9e20012",
                "timestamp": "2026-01-23T09:00:00Z",
                "asset": "SP500",
                "direction": "SELL",
                "confidence": 0.81,
                "horizon_hours": 2,
                "entry_price": 6890.0,
                "move_pct": 0.002,  # 0.2%
            },
        ]

    # -------------------------
    # 2) Optional: crypto-only
    # -------------------------
    if CRYPTO_ONLY:
        preds = [p for p in preds if _is_crypto_asset(p.get("asset", ""))]

    if not preds:
        print("No predictions to score (empty after filtering).")
        return

    # -------------------------
    # 3) Score each prediction
    # -------------------------
    scored_rows: List[Dict[str, Any]] = []

    for p in preds:
        # momentums uses Binance for crypto + Yahoo for others
        momentums = get_momentums(p, binance_client=binance_client)

        # scoring() already includes entry_quality (via your updated scoring.py)
        row = score_prediction(p, binance_client=binance_client, momentums=momentums)
        scored_rows.append(row)

    full = pd.DataFrame(scored_rows)

    # Ensure ranking col exists (fallback to old if not)
    if SCORE_COL not in full.columns and "confidence_reliability_score" in full.columns:
        print(f"⚠️ '{SCORE_COL}' not found. Falling back to 'confidence_reliability_score'.")
        score_col_used = "confidence_reliability_score"
    else:
        score_col_used = SCORE_COL

    # -------------------------
    # 4) Selection (rank by score_col_used)
    # -------------------------
    full = add_selection_flags(
        full,
        top_pct=TOP_PCT,
        score_col=score_col_used,
        min_score=MIN_SCORE,
        min_user_conf=MIN_USER_CONFIDENCE,
        min_structural=MIN_STRUCTURAL,
    )

    selected = get_selected(full)

    # -------------------------
    # 5) Export outputs
    # -------------------------
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    full_export = full.copy()
    for col in ["fundamental_breakdown", "technical_breakdown", "momentums", "entry_breakdown"]:
        if col in full_export.columns:
            full_export[col] = full_export[col].apply(_jsonify_cell)

    (out_dir / "full_ranked.csv").write_text(full_export.to_csv(index=False), encoding="utf-8")
    (out_dir / "full_ranked.json").write_text(full_export.to_json(orient="records", indent=2), encoding="utf-8")

    if selected is not None and not selected.empty:
        selected_export = selected.copy()
        for col in ["fundamental_breakdown", "technical_breakdown", "momentums", "entry_breakdown"]:
            if col in selected_export.columns:
                selected_export[col] = selected_export[col].apply(_jsonify_cell)

        (out_dir / "selected.csv").write_text(selected_export.to_csv(index=False), encoding="utf-8")
        (out_dir / "selected.json").write_text(selected_export.to_json(orient="records", indent=2), encoding="utf-8")
        print("✅ Saved SELECTED to: outputs/selected.csv and outputs/selected.json")
    else:
        print("ℹ️ No SELECTED rows to export (empty selection).")

    print("✅ Saved FULL ranked to: outputs/full_ranked.csv and outputs/full_ranked.json")

    # -------------------------
    # 6) Print table
    # -------------------------
    cols = [
        "user_id", "submission_id", "asset", "direction",
        "user_confidence",
        "technical_bias", "technical_alignment",
        "weighted_momentum", "momentum_alignment",
        "fundamental_score",
        "structural_reliability",
        "confidence_reliability_score",
        "entry_price", "move_pct", "entry_score",
        "final_reliability_score",
        "reliability",
        "selected",
    ]
    cols = [c for c in cols if c in full.columns]

    print("\n=== FULL RANKED ===")
    print(full[cols].sort_values(score_col_used, ascending=False).to_string(index=False))

    print(f"\n=== SELECTED (top {int(TOP_PCT * 100)}% among users with confidence >= {MIN_USER_CONFIDENCE}) ===")
    if selected is None or selected.empty:
        print("No signals passed the filter.")
    else:
        cols2 = [c for c in cols if c in selected.columns]
        print(selected[cols2].sort_values(score_col_used, ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()