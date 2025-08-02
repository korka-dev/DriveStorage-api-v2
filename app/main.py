
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console
from app.mongo_connect import connect_database, disconnect_from_database

from app.routers import user, auth, storage

console = Console()


@asynccontextmanager
async def lifespan(_app: FastAPI):

    console.print(":banana: [cyan underline]Drive Storage Api is starting ...[/]")
    connect_database()
    yield
    console.print(":mango: [bold red underline]Drive Storage Api shutting down ...[/]")
    disconnect_from_database()

app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ajout de la route racine
@app.get("/")
async def root():
    return {
        "message": "Bienvenue sur l'API Drive Storae pour la gestion de vos fichiers !",
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs"
    }

# Inclusion des routeurs
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(storage.router)





