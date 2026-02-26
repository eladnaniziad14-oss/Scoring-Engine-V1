# Scoring Engine (Metamodel) — v2 (Reliability + Entry Quality)

This project ranks user market predictions by **confidence reliability** — i.e., how well a user's stated confidence aligns with:
- **Technical Bias** (multi-timeframe indicators)
- **Fundamentals** (hybrid sentiment/macro layer)
- **Momentum Alignment** (hourly + daily momentum)
- **Entry + Target Quality** (entry feasibility, move realism, optional Binance liquidity proxy)

The output is a ranked table and exported files (`CSV` + `JSON`) showing:
- which predictions are most **reliable**
- which predictions are **selected** (top % after gating rules)

---

## What the model does (high level)

### 1) Structural Reliability (0..1)
For each prediction, we compute alignment scores:

- **technical_alignment**: does the direction match the technical bias?
- **momentum_alignment**: does the direction match momentum?
- **fundamental_score**: macro/news/analyst/crypto mood support
- **hourly_time_consistency**: stability between short momentum windows

Then we combine them into:

`structural_reliability = 0.45*momentum_alignment + 0.35*technical_alignment + 0.15*fundamental_score + 0.05*time_consistency`

### 2) Confidence Reliability Score (0..1)
User reports confidence, we validate it:

`confidence_reliability_score = user_confidence * structural_reliability`

### 3) Entry Quality Score (0..1)
If a prediction includes:
- `entry_price`
- `move_pct` (optional predicted move percentage)
- `horizon_hours`

We score how logical it is using:
- **bootstrap p_touch** (probability entry is reachable within horizon)
- **p_reach_target** (if move_pct exists)
- **ATR/VWAP precision scoring**
- **move realism** (volatility-scaled plausibility)
- **liquidity proxy** (Binance only, optional; neutral otherwise)

### 4) Final Reliability Score (0..1)
Entry quality is applied as a **soft multiplier**, not dominating:

`final_reliability_score = confidence_reliability_score * (0.7 + 0.3*entry_score)`

This final score is the recommended ranking score.

---

## Folder structure

Typical core files:
- `main.py` — loads predictions, runs scoring, exports outputs
- `scoring.py` — combines technical/fundamental/momentum + entry quality
- `technical_bias.py` — multi-timeframe technical bias (daily-weighted)
- `fundamentals.py` — hybrid fundamentals layer (VADER/FinBERT + macro/events)
- `market_data.py` — OHLCV fetch + momentum + ATR + entry inputs
- `entry_quality.py` — entry/target scoring (bootstrap + ATR/VWAP + realism)
- `ranking.py` — selection logic (top % after gates)
- `asset_registry.py` — resolves canonical asset symbols and data sources
- `data_loader.py` — loads `predictions.json`
- `utils.py` — time parsing helpers

Outputs:
- `outputs/full_ranked.csv`
- `outputs/full_ranked.json`
- `outputs/selected.csv`
- `outputs/selected.json`

---

## Setup

### 1) Create a virtual environment
```bash
python -m venv .venv