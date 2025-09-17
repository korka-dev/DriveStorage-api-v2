from typing import Annotated, List
from fastapi import APIRouter, HTTPException, UploadFile, Depends, status
from fastapi.responses import StreamingResponse
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from sqlalchemy.ext.asyncio import AsyncSession
from app.mongo_connect import iter_chunks, get_gridfs_bucket
from app.models.file import Directory, File
from app.models.user import User
from app.schemas.file import DirectoryOut, FileOut
from app.utils import get_filename, check_storage_quota, calculate_user_storage_usage
from app.oauth2 import get_current_user
from app.config import settings
from app.mongo_connect import iter_chunks, grid_fs_bucket
from app.postgres_connect import get_db_session

router = APIRouter(prefix="/files", tags=["Storage"])


# -------------------- Directory --------------------
@router.post("/{directory}", response_model=DirectoryOut, status_code=status.HTTP_201_CREATED)
async def create_directory(
    directory: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not directory:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nom du dossier est requis")

    existing_dir = await Directory.find_one(
        Directory.dir_name == directory,
        Directory.owner_id == str(current_user.id)
    )
    if existing_dir:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Le dossier existe déjà")

    new_dir = Directory(
        dir_name=directory,
        owner_id=str(current_user.id),
        owner=current_user.name,
        created_at=datetime.utcnow()
    )
    await new_dir.insert()
    return new_dir


@router.get("/directories", response_model=List[DirectoryOut], status_code=status.HTTP_200_OK)
async def get_user_directories(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return await Directory.find(Directory.owner_id == str(current_user.id)).to_list()


@router.patch("/rename-directory/{current_directory_name}", status_code=status.HTTP_200_OK)
async def rename_directory(
    current_directory_name: str,
    new_directory_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not new_directory_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouveau nom du dossier est requis")

    existing_dir = await Directory.find_one(
        Directory.dir_name == current_directory_name,
        Directory.owner_id == str(current_user.id)
    )
    if not existing_dir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Le dossier actuel n'existe pas")

    if await Directory.find_one(
        Directory.dir_name == new_directory_name,
        Directory.owner_id == str(current_user.id)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un dossier avec ce nom existe déjà")

    existing_dir.dir_name = new_directory_name
    await existing_dir.save()
    return {"detail": "Dossier renommé avec succès"}


# -------------------- Files --------------------
@router.post("/upload/{directory}", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    directory: str,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    gridfs_bucket: Annotated[AsyncIOMotorGridFSBucket, Depends(get_gridfs_bucket)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    filename: str | None = None,
    keep: bool = True,
):
    filename = filename or file.filename
    if '.' not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Nom de fichier invalide : {filename}"
        )

    # Vérifie si le dossier existe
    found_dir = await Directory.find_one(
        Directory.dir_name == directory,
        Directory.owner_id == str(current_user.id)
    )
    if not found_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le dossier '{directory}' n'existe pas"
        )

    # Lire le contenu pour obtenir la taille
    content = await file.read()
    file_size_bytes = len(content)
    
    can_upload = await check_storage_quota(
        str(current_user.id), 
        file_size_bytes, 
        db
    )
    
    if not can_upload:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Quota de stockage dépassé. Veuillez upgrader votre abonnement."
        )

    # Vérifie si le fichier existe déjà
    found_file = await File.find_one(
        File.file_name == filename,
        File.parent.id == found_dir.id
    )
    if found_file:
        if keep:
            filename = get_filename(filename)
        else:
            await found_file.delete()
            await gridfs_bucket.delete(found_file.gridfs_id)

    # Upload vers GridFS
    upload_stream = gridfs_bucket.open_upload_stream(filename, metadata={
        "owner_id": str(current_user.id),
        "directory": directory
    })
    await upload_stream.write(content)
    await upload_stream.close()

    # Créer le document File
    new_file = File(
        file_name=filename,
        content_type=file.content_type,
        owner_id=str(current_user.id),
        owner=current_user.name,
        created_at=datetime.utcnow(),
        parent=found_dir,
        gridfs_id=upload_stream._id,
        file_size_bytes=file_size_bytes
    )
    await new_file.insert()
    
    await calculate_user_storage_usage(str(current_user.id), db, gridfs_bucket)
    
    return new_file


@router.get("/download/{directory}/{filename}", status_code=status.HTTP_200_OK)
async def download_file(
    directory: str,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    found_dir = await Directory.find_one(
        Directory.dir_name == directory,
        Directory.owner_id == str(current_user.id)
    )
    if not found_dir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dossier '{directory}' introuvable")

    file = await File.find_one(
        File.file_name == filename,
        File.parent.id == found_dir.id
    )
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fichier '{filename}' introuvable dans '{directory}'")

    return StreamingResponse(
        iter_chunks(file.gridfs_id, settings.chunk_size),
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename={file.file_name}"}
    )

@router.get("/list", response_model=List[FileOut], status_code=status.HTTP_200_OK)
async def get_files_in_directory(
    current_user: Annotated[User, Depends(get_current_user)],
    directory: str | None = None,
    limit: int = 5,
    skip: int = 0,
):
    if directory:
        found_dir = await Directory.find_one(
            Directory.dir_name == directory,
            Directory.owner_id == str(current_user.id)
        )
        if not found_dir:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dossier '{directory}' introuvable"
            )
        files = await File.find(
            File.parent.id == found_dir.id,
            File.owner_id == str(current_user.id)
        ).skip(skip).limit(limit).to_list(length=limit)
    else:
        files = await File.find(
            File.owner_id == str(current_user.id)
        ).skip(skip).limit(limit).to_list(length=limit)

    # Peupler parent avec fetch()
    for f in files:
        if f.parent:
            f.parent = await f.parent.fetch()

    return files


@router.delete("/delete/{directory}/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    directory: str,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    gridfs_bucket: Annotated[AsyncIOMotorGridFSBucket, Depends(get_gridfs_bucket)],
):
    found_dir = await Directory.find_one(
        Directory.dir_name == directory,
        Directory.owner_id == str(current_user.id)
    )
    if not found_dir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                            detail=f"Dossier '{directory}' introuvable")

    file = await File.find_one(
        File.file_name == filename,
        File.parent.id == found_dir.id
    )
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fichier '{filename}' introuvable dans '{directory}'")

    if file.owner_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non autorisé à supprimer ce fichier")

    await gridfs_bucket.delete(file.gridfs_id)
    await file.delete()
    
    await calculate_user_storage_usage(str(current_user.id), db, gridfs_bucket)
    
    return {"detail": "Fichier supprimé avec succès"}

