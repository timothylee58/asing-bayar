import httpx
from loguru import logger

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_expo_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """Send push notifications via Expo Push API (no SDK needed, plain HTTP)."""
    if not tokens:
        return

    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
            "channelId": "bayarlah",
        }
        for token in tokens
        if token.startswith("ExponentPushToken[")
    ]

    if not messages:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={"Content-Type": "application/json"},
            )
            res.raise_for_status()
            result = res.json()
            for item in result.get("data", []):
                if item.get("status") == "error":
                    logger.warning(f"Push failed: {item.get('message')}")
    except Exception as e:
        logger.error(f"Expo push error: {e}")
