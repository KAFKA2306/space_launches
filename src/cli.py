#!/usr/bin/env python3
"""TraHist CLI - User Story Based Commands"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="TraHist: Trade History Analyzer & Portfolio Manager",
        epilog="Use '%(prog)s <command> --help' for command-specific help.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import commands module dynamically to avoid circular imports
    from src.commands import fetch, portfolio, report, unified

    # Register subcommands with user story-based names
    fetch.register(subparsers, command_name="fetch")
    portfolio.register(subparsers, command_name="holdings")
    unified.register(subparsers, command_name="metrics")
    report.register(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to the selected command's run function
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
