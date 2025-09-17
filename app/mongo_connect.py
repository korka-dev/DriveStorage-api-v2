from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from beanie import init_beanie
from app.models.file import Directory, File
from app.config import settings

client: AsyncIOMotorClient = None
db = None
grid_fs_bucket: AsyncIOMotorGridFSBucket = None

async def connect_database():
    global client, db, grid_fs_bucket
    client = AsyncIOMotorClient(settings.mongo_database_url)
    db = client.get_default_database()
    grid_fs_bucket = AsyncIOMotorGridFSBucket(db)

    await init_beanie(
        database=db,
        document_models=[Directory, File]
    )

async def disconnect_from_database():
    global client
    if client:
        client.close()

async def iter_chunks(file_id, chunk_size: int = 1024):
    stream = await grid_fs_bucket.open_download_stream(file_id)
    while True:
        chunk = await stream.read(chunk_size)
        if not chunk:
            break
        yield chunk

def get_gridfs_bucket() -> AsyncIOMotorGridFSBucket:
    """Retourne l'instance du GridFS bucket."""
    global grid_fs_bucket
    if grid_fs_bucket is None:
        raise RuntimeError("GridFS bucket non initialisé. Vérifiez la connexion à la base de données.")
    return grid_fs_bucket
