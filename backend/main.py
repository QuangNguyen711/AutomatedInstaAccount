from __future__ import annotations

import uvicorn


def main() -> None:
    # reload=True must stay off: on Windows, uvicorn's --reload/reload mode runs the app under
    # a SelectorEventLoop instead of ProactorEventLoop, and SelectorEventLoop can't spawn
    # subprocesses at all — breaks Playwright's Chromium launch with a NotImplementedError
    # (confirmed live; this was the cause of a 500 on every search until traced back here).
    uvicorn.run("backend.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
