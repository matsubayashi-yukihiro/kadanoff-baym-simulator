import os

import uvicorn

from backend.app.main import app


def main() -> None:
    host = os.getenv("TDKB_HOST", "127.0.0.1")
    port = int(os.getenv("TDKB_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
