import os
from functools import lru_cache

from repository.mongo import MongoRepository


@lru_cache
def get_repo() -> MongoRepository:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db = os.getenv("MONGO_DB", "vinyl_recko")
    return MongoRepository(uri=uri, database=db)
