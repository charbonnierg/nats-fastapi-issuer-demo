import typing as t

from fastapi import Depends
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient
from wire import get_hook


def get_database(name: t.Optional[str] = None) -> t.Any:
    """Access a MongoDB database from an API endpoint.

    If no database name is provided, default database is returned
    """

    def database_dependency(
        client: AgnosticClient = get_hook(AsyncIOMotorClient),
    ) -> AgnosticDatabase:
        if name is None:
            return client.get_default_database()
        return client[name]

    return Depends(database_dependency)


def get_collection(name: str, db: t.Optional[str] = None) -> t.Any:
    """Access a MongoDB collection from an API endpoint"""

    async def collection_dependency(
        database: AgnosticDatabase = get_database(db),
    ) -> AgnosticCollection:
        return database[name]

    return Depends(collection_dependency)
