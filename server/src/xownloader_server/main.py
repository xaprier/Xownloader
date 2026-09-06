from fastapi import FastAPI

from xownloader_server import __version__

app = FastAPI(
    title="Xownloader API",
    version=__version__,
    description="Server API for policy-controlled media downloads.",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "xownloader-server", "version": __version__}
