from __future__ import annotations

import pandas as pd


def add_selection_flags(
    df: pd.DataFrame,
    *,
    top_pct: float = 0.30,
    score_col: str = "final_reliability_score",  # ✅ default to new score
    # Optional gates (set to None to disable)
    min_score: float | None = None,
    min_user_conf: float | None = 0.70,
    min_structural: float | None = 0.55,
) -> pd.DataFrame:
    """
    Adds a boolean 'selected' column.

    Selection logic:
    1) Apply optional gates:
       - min_user_conf on df['user_confidence']
       - min_structural on df['structural_reliability']
       - min_score on df[score_col]
    2) From remaining rows, select top_pct by score_col.
    """
    out = df.copy()
    out["selected"] = False

    if out.empty or score_col not in out.columns:
        return out

    mask = pd.Series(True, index=out.index)

    if min_user_conf is not None and "user_confidence" in out.columns:
        mask &= out["user_confidence"] >= float(min_user_conf)

    if min_structural is not None and "structural_reliability" in out.columns:
        mask &= out["structural_reliability"] >= float(min_structural)

    if min_score is not None:
        mask &= out[score_col] >= float(min_score)

    candidates = out[mask].sort_values(score_col, ascending=False)

    if candidates.empty:
        return out

    n_select = max(1, int(round(len(candidates) * float(top_pct))))
    selected_idx = candidates.head(n_select).index
    out.loc[selected_idx, "selected"] = True

    return out


def get_selected(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "selected" not in df.columns:
        return pd.DataFrame()
    return df[df["selected"] == True].copy()