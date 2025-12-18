#!/usr/bin/env python3
import sys
import argparse
from src.commands import fetch, portfolio, unified

def main():
    parser = argparse.ArgumentParser(
        description="TraHist: Trade History Analyzer & Portfolio Manager",
        epilog="Use '%(prog)s <command> --help' for command-specific help."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register subcommands
    fetch.register(subparsers)
    portfolio.register(subparsers)
    unified.register(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to the selected command's run function
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
