"""
Entry point to launch the Nebula Supermarket Web Dashboard and AI Copilot server.
Usage:
    python run_web.py
    or
    python run_web.py --port 8000 --host 0.0.0.0
"""
import sys
import os
import argparse
import uvicorn

# UTF-8 encoding safeguard for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Run Nebula Supermarket Web Dashboard & AI Copilot")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    print("=" * 75)
    print("🏬  SUPERMARKET OPERATIONS - WEB DASHBOARD & ASSISTANT")
    print("=" * 75)
    print(f"Server starting on http://{args.host}:{args.port}")
    print("• Interactive Assistant Copilot: Enabled")
    print("• Real-Time Telemetry Stream: Enabled (/ws)")
    print("• Inventory & Catalog Management: Enabled")
    print("• Automated GST Invoicing (PDF) & Presentation Decks: Enabled")
    print("=" * 75)

    uvicorn.run("web.server:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
