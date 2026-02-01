"""
Unified runner for full sentiment pipeline → composite score.
Make sure your pipelines have already generated fresh *_sentiment files
inside data/<pipeline>/ directories.
"""

import logging
from core.orchestrator import SentimentOrchestrator

def main():
    logging.basicConfig(level=logging.INFO)

    print("\n🚀 Running Composite Crypto Sentiment Engine...\n")

    orchestrator = SentimentOrchestrator()

    print("📊 Dimensions contributing:")
    breakdown = orchestrator.debug_breakdown()
    for sym, dims in breakdown.items():
        print(f"\n{sym}:")
        for src, score in dims.items():
            print(f"  {src:<12} {score:+.4f}")

    print("\n🧮 Weighted Composite Scores:")
    scores = orchestrator.composite_scores()
    for sym, vals in scores.items():
        print(f"\n{sym}:")
        print(f"  sentiment_score: {vals['sentiment_score']:+.3f}")
        print(f"  confidence:     {vals['confidence']:.2f}")
        print(f"  regime:         {vals['regime']}")


    print("\n✨ Done!\n")


if __name__ == "__main__":
    main()
