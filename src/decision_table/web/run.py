"""Entry point for the Decision Table web editor."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Decision Table Web Editor")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8050, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    from decision_table.web.app import app

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
