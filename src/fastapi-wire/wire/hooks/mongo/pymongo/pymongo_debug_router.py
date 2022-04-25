from time import time
from typing import Any, Dict

from fastapi import APIRouter
from pymongo import MongoClient
from wire import get_hook

from .pymongo_utils import get_replicate_set_config, get_replicate_set_status

router = APIRouter(prefix="/debug/pymongo", tags=["Debug", "MongoDB"])


@router.get("/server/ping", summary="Ping MongoDB server")
def ping(client: MongoClient = get_hook(MongoClient)) -> Dict[str, Any]:
    """Ping MongoDB server"""
    start = time()
    pong = client.admin.command("ping")
    end = time()
    rtt_ms = (end - start) * 1000
    return {"rtt": format(rtt_ms, ".3f") + "ms", "pong": pong}


@router.get("/server/infos", summary="Get MongoDB server infos")
def get_server_infos(client: MongoClient = get_hook(MongoClient)) -> Dict[str, Any]:
    """Get MongoDB server infos"""
    return client.server_info()


@router.get("/rs/status", summary="Get MongoDB replica set status")
def get_rs_status(client: MongoClient = get_hook(MongoClient)) -> Dict[str, Any]:
    """Get replica set status"""
    return get_replicate_set_status(client)


@router.get("/rs/config", summary="Get MongoDB replica set configuration")
def get_rs_config(client: MongoClient = get_hook(MongoClient)) -> Dict[str, Any]:
    """Get replica set configuration"""
    config = get_replicate_set_config(client)
    # Sanitize object ID
    config["config"]["settings"]["replicaSetId"] = str(
        config["config"]["settings"]["replicaSetId"]
    )
    # Return config as dict, FastAPI will handle JSON serialization
    return config
