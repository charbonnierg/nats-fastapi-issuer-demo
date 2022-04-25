import typing as t

from fastapi import APIRouter
from nats.aio.client import Client as NATSClient
from wire import get_hook

router = APIRouter(prefix="/debug/nats", tags=["Debug", "NATS"])


LABEL_TO_STATUS = {
    "DISCONNECTED": 0,
    "CONNECTED": 1,
    "CLOSED": 2,
    "RECONNECTING": 3,
    "CONNECTING": 4,
    "DRAINING_SUBS": 5,
    "DRAINING_PUBS": 6,
}
STATUS_TO_LABEL = {
    0: "DISCONNECTED",
    1: "CONNECTED",
    2: "CLOSED",
    3: "RECONNECTING",
    4: "CONNECTING",
    5: "DRAINING_SUBS",
    6: "DRAINING_PUBS",
}


@router.get("/server/infos", summary="Get server infos")
async def ping(client: NATSClient = get_hook(NATSClient)) -> t.Dict[str, t.Any]:
    """Ping NATS server"""
    return client._server_info


@router.get("/client/status", summary="Get client status")
async def get_client_status(
    client: NATSClient = get_hook(NATSClient),
) -> t.Dict[str, str]:
    """Get NATS client status"""
    return {"status": STATUS_TO_LABEL[client._status]}


@router.get("/client/stats", summary="Get client stats")
async def get_client_stats(
    client: NATSClient = get_hook(NATSClient),
) -> t.Dict[str, str]:
    """Get NATS client statistics"""
    return {"stats": client.stats}
