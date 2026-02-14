def momentum_5d(price_today: float, price_5d: float) -> float:
    return (price_today - price_5d) / price_5d * 100

def momentum_20d(price_today: float, price_20d: float) -> float:
    return (price_today - price_20d) / price_20d * 100

def momentum_40d(price_today: float, price_40d: float) -> float:
    return (price_today - price_40d) / price_40d * 100

def momentum_60d(price_today: float, price_60d: float) -> float:
    return (price_today - price_60d) / price_60d * 100

def instrument_skill_score(instrument_60d_accuracy: float, instrument_60d_sharpe: float, instrument_60d_count: int) -> float:
    return (instrument_60d_accuracy * 0.6 + instrument_60d_sharpe * 0.4) if instrument_60d_count >= 100 else 1

def session_skill_score(session_60d_accuracy: float, session_60d_sharpe: float, session_60d_count: int) -> float:
    return (session_60d_accuracy * 0.6 + session_60d_sharpe * 0.4) if session_60d_count >= 50 else 1

def news_skill_score(is_high_impact_news_hour: bool, news_hour_60d_accuracy: float, news_hour_60d_sharpe: float, news_hour_60d_count: int) -> float:
    return (news_hour_60d_accuracy * 0.6 + news_hour_60d_sharpe * 0.4) if is_high_impact_news_hour == True and news_hour_60d_count >= 30 else 1

def user_historical_performance_score(historical_accuracy: float, sharpe_ratio: float, VaR: float, bias_change_frequency: float, median_positive_excursion: float, median_negative_excursion: float) -> float:
    return (historical_accuracy * 0.4) + (sharpe_ratio * 0.2) - (VaR * 0.1) - (bias_change_frequency * 0.1) + ((median_positive_excursion - median_negative_excursion) * 0.1)

def risk_behavior_quality(sharpe_ratio: float, VaR: float, median_positive_excursion: float, median_negative_excursion: float, best_positive_excursion: float, worst_negative_excursion: float) -> float:
    return ((sharpe_ratio / max(abs(VaR),0.0001)) * 0.4) + ((median_positive_excursion / max(abs(median_negative_excursion),0.0001)) * 0.3) + ((best_positive_excursion / max(abs(worst_negative_excursion),0.0001)) * 0.3)

def base_confidence_ratio(momentum_20d: float, momentum_40d: float, momentum_60d: float, user_historical_performance_score: float, risk_behavior_quality: float) -> float:
    return ((momentum_20d * 0.2 + momentum_40d * 0.3 + momentum_60d * 0.5) / 100) * user_historical_performance_score * risk_behavior_quality

def context_adjusted_confidence(base_confidence_ratio: float, instrument_skill_score: float, session_skill_score: float, news_skill_score: float) -> float:
    return base_confidence_ratio * instrument_skill_score * session_skill_score * news_skill_score

def clip(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))

def confidence_ratio(context_adjusted_confidence: float) -> float:
    return clip(context_adjusted_confidence, 0, 1)

def replace_weaker_signal(confidence_ratio: float, old_confidence: float) -> bool:
    return confidence_ratio - old_confidence >= 0.10 if old_confidence is not None else False

def correlation_penalty(correlation: float) -> float:
    return max(0, (correlation - 0.7) / 0.3) * 0.4

def final_score(confidence_ratio: float, instrument_skill_score: float, risk_behavior_quality: float, user_historical_performance_score: float, session_skill_score: float, news_skill_score: float, correlation_penalty: float) -> float:
    return ((confidence_ratio * 0.35) + (instrument_skill_score * 0.20) + (risk_behavior_quality * 0.20) + (user_historical_performance_score * 0.15)) * session_skill_score * news_skill_score * (1 - correlation_penalty)

def main(data: dict) -> dict:
    momentum_5d_val = momentum_5d(data["market_data"]["price_today"], data["market_data"]["price_5d"])
    momentum_20d_val = momentum_20d(data["market_data"]["price_today"], data["market_data"]["price_20d"])
    momentum_40d_val = momentum_40d(data["market_data"]["price_today"], data["market_data"]["price_40d"])
    momentum_60d_val = momentum_60d(data["market_data"]["price_today"], data["market_data"]["price_60d"])
    instrument_skill_score_val = instrument_skill_score(data["predictor_data"]["instrument_60d_accuracy"], data["predictor_data"]["instrument_60d_sharpe"], data["predictor_data"]["instrument_60d_count"])
    session_skill_score_val = session_skill_score(data["predictor_data"]["session_60d_accuracy"], data["predictor_data"]["session_60d_sharpe"], data["predictor_data"]["session_60d_count"])
    news_skill_score_val = news_skill_score(data["market_data"]["is_high_impact_news_hour"], data["predictor_data"].get("news_hour_60d_accuracy"), data["predictor_data"].get("news_hour_60d_sharpe"), data["predictor_data"].get("news_hour_60d_count"))
    user_historical_performance_score_val = user_historical_performance_score(data["predictor_data"]["historical_accuracy"], data["predictor_data"]["sharpe_ratio"], data["predictor_data"]["VaR"], data["predictor_data"]["bias_change_frequency"], data["predictor_data"]["median_positive_excursion"], data["predictor_data"]["median_negative_excursion"])
    risk_behavior_quality_val = risk_behavior_quality(data["predictor_data"]["sharpe_ratio"], data["predictor_data"]["VaR"], data["predictor_data"]["median_positive_excursion"], data["predictor_data"]["median_negative_excursion"], data["predictor_data"]["best_positive_excursion"], data["predictor_data"]["worst_negative_excursion"])
    base_confidence_ratio_val = base_confidence_ratio(momentum_20d_val, momentum_40d_val, momentum_60d_val, user_historical_performance_score_val, risk_behavior_quality_val)
    context_adjusted_confidence_val = context_adjusted_confidence(base_confidence_ratio_val, instrument_skill_score_val, session_skill_score_val, news_skill_score_val)
    confidence_ratio_val = confidence_ratio(context_adjusted_confidence_val)
    replace_weaker_signal_val = replace_weaker_signal(confidence_ratio_val, data["previous_confidence"].get("old_confidence"))
    correlation_penalty_val = correlation_penalty(data["correlation_matrix"]["correlation"])
    final_score_val = final_score(confidence_ratio_val, instrument_skill_score_val, risk_behavior_quality_val, user_historical_performance_score_val, session_skill_score_val, news_skill_score_val, correlation_penalty_val)
    return {
        "confidence_ratio": confidence_ratio_val,
        "final_score": final_score_val,
        "selected_signals": {
            "replace_weaker_signal": replace_weaker_signal_val,
            "correlation_penalty": correlation_penalty_val
        }
    }