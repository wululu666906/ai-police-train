"""Offline regression + optional live-turn validation for state influence engine."""

from __future__ import annotations

import argparse
import json

from services.state_influence_metrics import run_regression_suite, simulate_state_influence


def main() -> None:
    parser = argparse.ArgumentParser(description="State influence A/B regression report")
    parser.add_argument("--emotion", type=int, default=None)
    parser.add_argument("--cooperation", type=int, default=None)
    parser.add_argument("--risk", type=int, default=None)
    parser.add_argument("--clarity", type=int, default=None)
    parser.add_argument("--message", type=str, default="")
    args = parser.parse_args()

    report = run_regression_suite()
    print("=== Regression suite ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.emotion is not None:
        preview = simulate_state_influence(
            {
                "emotion": args.emotion,
                "cooperation": args.cooperation if args.cooperation is not None else 50,
                "risk": args.risk if args.risk is not None else 50,
                "clarity": args.clarity if args.clarity is not None else 50,
            },
            user_message=args.message,
        )
        print("\n=== Manual simulate ===")
        print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
