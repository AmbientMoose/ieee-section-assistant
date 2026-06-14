"""
Command-line interface for the IEEE Section Operations Assistant.

Usage:
    python cli.py                 # interactive Q&A loop
    python cli.py "your question" # one-shot
"""

import sys

import config
from retriever import Index
from llm import synthesize

BANNER = r"""
============================================================
  IEEE Section Operations Assistant  (prototype)
  Grounded in public IEEE documents - answers cite sources.
============================================================
"""


def load_index() -> Index:
    if not config.INDEX_PATH.exists():
        print("No index found. Run:  python ingest.py", file=sys.stderr)
        sys.exit(1)
    return Index.load(config.INDEX_PATH)


def answer(index: Index, question: str) -> str:
    hits = index.search(question, top_k=config.TOP_K)
    return synthesize(question, hits)


def main():
    index = load_index()
    if len(sys.argv) > 1:
        print(answer(index, " ".join(sys.argv[1:])))
        return
    print(BANNER)
    print(f"Indexed {index.meta['n_chunks']} passages. Type a question "
          f"(or 'quit').\n")
    while True:
        try:
            q = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"quit", "exit", "q"}:
            break
        if not q:
            continue
        print("\n" + answer(index, q) + "\n")


if __name__ == "__main__":
    main()
