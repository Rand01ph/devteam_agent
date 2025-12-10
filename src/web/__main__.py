"""Web UI entry point."""

import uvicorn


def main():
    """Run the web server."""
    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
