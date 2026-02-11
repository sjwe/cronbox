from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request, api_key: str | None = Security(api_key_header)
):
    settings = request.app.state.settings
    if not settings.api_key:
        return  # No auth configured

    # Check X-API-Key header
    if api_key == settings.api_key:
        return

    # Check Authorization: Bearer header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == settings.api_key:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
