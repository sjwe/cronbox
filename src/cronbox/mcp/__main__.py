"""CLI entrypoint: python -m cronbox.mcp"""

import argparse
import logging

from cronbox.mcp.server import mcp

logging.basicConfig(level=logging.INFO)


def main():
    parser = argparse.ArgumentParser(description="cronbox MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9100,
        help="Port for HTTP/SSE transport (default: 9100)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP/SSE transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    kwargs = {}
    if args.transport in ("http", "sse"):
        kwargs["host"] = args.host
        kwargs["port"] = args.port

    mcp.run(transport=args.transport, **kwargs)


if __name__ == "__main__":
    main()
