from time import time
from typing import Any, Dict

from fastapi import APIRouter
from motor.core import AgnosticClient
from motor.motor_asyncio import AsyncIOMotorClient
from wire import get_hook

from .motor_utils import get_replicate_set_config, get_replicate_set_status

router = APIRouter(prefix="/debug/motor", tags=["Debug", "MongoDB"])


@router.get("/server/ping", summary="Ping MongoDB server")
async def ping(client: AgnosticClient = get_hook(AsyncIOMotorClient)) -> Dict[str, Any]:
    """Ping MongoDB server"""
    start = time()
    pong = await client.admin.command("ping")
    end = time()
    rtt_ms = (end - start) * 1000
    return {"rtt": format(rtt_ms, ".3f") + "ms", "pong": pong}


@router.get("/server/infos", summary="Get MongoDB server infos")
async def get_server_infos(
    client: AgnosticClient = get_hook(AsyncIOMotorClient),
) -> Dict[str, Any]:
    """Get MongoDB server infos"""
    return await client.server_info()


@router.get("/rs/status", summary="Get MongoDB replica set status")
async def get_rs_status(
    client: AgnosticClient = get_hook(AsyncIOMotorClient),
) -> Dict[str, Any]:
    """Get replica set status"""
    return await get_replicate_set_status(client)


@router.get("/rs/config", summary="Get MongoDB replica set configuration")
async def get_rs_config(
    client: AgnosticClient = get_hook(AsyncIOMotorClient),
) -> Dict[str, Any]:
    """Get replica set configuration"""
    config = await get_replicate_set_config(client)
    # Sanitize object ID
    config["config"]["settings"]["replicaSetId"] = str(
        config["config"]["settings"]["replicaSetId"]
    )
    # Return config as dict, FastAPI will handle JSON serialization
    return config
