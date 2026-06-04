"""
main.py
-------
Orchestration entry point for the Incident Analytics Pipeline.

Workflow
--------
  1. Load and process the raw incident Excel log.
  2. Display the monthly aggregation table.
  3. Upsert the monthly summaries into the Milvus vector store.
  4. Build the unified AgentExecutor (Pandas + Milvus tools).
  5. Launch an interactive CLI loop for natural-language queries.

Usage
-----
    # Minimal — uses all defaults
    python main.py --file incidents.xlsx

    # Override sheet and skip Milvus upsert (e.g. Milvus already populated)
    python main.py --file incidents.xlsx --sheet "Sheet2" --no-upsert

    # Run in batch mode (non-interactive) with a single question
    python main.py --file incidents.xlsx --query "How does this month compare to last?"

Environment Variables (required)
---------------------------------
    OPENAI_API_KEY      – OpenAI API key (for LLM + embeddings)
    MILVUS_URI          – Milvus URI (default: http://localhost:19530)
    MILVUS_TOKEN        – Milvus/Zilliz token (optional, for cloud)
    MILVUS_COLLECTION   – Collection name (default: incident_monthly_summaries)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import pandas as pd

from incident_processor import process_incident_log
from milvus_store import get_vector_store, store_monthly_summary
from agent import build_agent, ask

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

def _check_env() -> None:
    """Warn about missing required environment variables."""
    missing = [v for v in ["OPENAI_API_KEY"] if not os.environ.get(v)]
    if missing:
        logger.error(
            "Missing required environment variable(s): %s\n"
            "Set them before running: export OPENAI_API_KEY=sk-...",
            ", ".join(missing),
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incident Analytics Pipeline — LangChain + Milvus",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the raw incident log Excel file (.xlsx)",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or zero-based index to read from the Excel file",
    )
    parser.add_argument(
        "--no-upsert",
        action="store_true",
        default=False,
        help="Skip upserting monthly summaries into Milvus (use if already stored)",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Run a single query in batch mode and exit (non-interactive)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model name for the agent LLM",
    )
    parser.add_argument(
        "--milvus-k",
        type=int,
        default=3,
        help="Number of historical reports to retrieve per similarity search",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_monthly_table(monthly_df: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("  MONTHLY INCIDENT AGGREGATION")
    print("=" * 70)
    # Limit display width for readability
    with pd.option_context("display.max_columns", 20, "display.width", 120):
        print(monthly_df.to_string())
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Interactive CLI loop
# ---------------------------------------------------------------------------

def _run_interactive(agent_executor) -> None:
    print("\n💬  Incident Analytics Agent — Interactive Mode")
    print("    Type your question and press Enter.  Type 'exit' or 'quit' to stop.\n")

    chat_history: list = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break

        answer = ask(agent_executor, user_input, chat_history=chat_history)
        print(f"\nAgent: {answer}\n")

        # Maintain a sliding window of 10 exchanges to avoid token overflow
        chat_history.append({"role": "user", "content": user_input})
        chat_history.append({"role": "assistant", "content": answer})
        if len(chat_history) > 20:
            chat_history = chat_history[-20:]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    _check_env()

    # ── Step 1: Process the incident log ─────────────────────────────────
    logger.info("Processing incident log: %s", args.file)
    categorized_df, monthly_df = process_incident_log(args.file, sheet_name=args.sheet)
    _print_monthly_table(monthly_df)

    # ── Step 2: Upsert monthly summaries into Milvus ─────────────────────
    if not args.no_upsert:
        logger.info("Connecting to Milvus and upserting monthly summaries …")
        vector_store = get_vector_store()
        store_monthly_summary(monthly_df, vector_store=vector_store)
        logger.info("Milvus upsert complete.")
    else:
        logger.info("Skipping Milvus upsert (--no-upsert flag set).")

    # ── Step 3: Build the agent ───────────────────────────────────────────
    logger.info("Building AgentExecutor …")
    agent_executor = build_agent(
        categorized_df=categorized_df,
        monthly_df=monthly_df,
        model=args.model,
        milvus_k=args.milvus_k,
    )

    # ── Step 4: Run in batch or interactive mode ──────────────────────────
    if args.query:
        answer = ask(agent_executor, args.query)
        print(f"\nAgent: {answer}\n")
    else:
        _run_interactive(agent_executor)


if __name__ == "__main__":
    main()
