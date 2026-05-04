"""Inspect a legacy pickle chat history file for debugging/migration."""
from __future__ import annotations

import pickle
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
LEGACY_PICKLE = ROOT_DIR / "data" / "runtime" / "chat_history" / "kiet.pkl"


def main() -> None:
    if not LEGACY_PICKLE.exists():
        raise FileNotFoundError(f"Legacy pickle file not found: {LEGACY_PICKLE}")

    with open(LEGACY_PICKLE, "rb") as f:
        data = pickle.load(f)

    for i, turn in enumerate(data):
        if turn.get("role") == "assistant" and "code" in turn:
            print(f"--- Code from turn {i} ---")
            print(turn["code"])
            print("---------------------------\n")


if __name__ == "__main__":
    main()
