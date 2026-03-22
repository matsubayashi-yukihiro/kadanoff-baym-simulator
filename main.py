import os

import uvicorn


def main() -> None:
    host = os.getenv("TDKB_HOST", "127.0.0.1")
    port = int(os.getenv("TDKB_PORT", "8000"))
    reload = os.getenv("TDKB_RELOAD", "false").lower() == "true"
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
