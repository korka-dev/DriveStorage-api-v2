from typing import Annotated, List
from fastapi import APIRouter, HTTPException, UploadFile, Depends, status
from fastapi.responses import StreamingResponse

from app.models.file import Directory, File
from app.models.user import User
from app.schemas.file import DirectoryOut, FileOut
from app.utils import get_filename
from app.oauth2 import get_current_user
from app.config import settings
from app.mongo_connect import iter_chunks

router = APIRouter(prefix="/files", tags=["Storage"])


@router.post("/{directory}", response_model=DirectoryOut, status_code=status.HTTP_201_CREATED)
async def create_directory(
    directory: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not directory:
        raise HTTPException(status_code=400, detail="Le nom du dossier est requis")

    existing_dir = Directory.objects(dir_name=directory, owner_id=str(current_user.id)).first()

    if existing_dir:
        raise HTTPException(status_code=409, detail="Le dossier existe déjà")

    new_dir = Directory(dir_name=directory, owner_id=str(current_user.id), owner=current_user.name)
    new_dir.save()

    return new_dir


@router.get("/directories", response_model=List[DirectoryOut])
async def get_user_directories(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return Directory.objects(owner_id=str(current_user.id)).all()


@router.post("/upload/{directory}", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    directory: str,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    filename: str | None = None,
    keep: bool = True,
):
    filename = filename or file.filename

    if '.' not in filename:
        raise HTTPException(status_code=400, detail=f"Nom de fichier invalide : {filename}")

    found_dir = Directory.objects(dir_name=directory, owner_id=str(current_user.id)).first()
    if not found_dir:
        found_dir = Directory(dir_name=directory, owner_id=str(current_user.id), owner=current_user.name)
        found_dir.save()

    found_file = File.objects(file_name=filename, parent=found_dir).first()
    if found_file:
        if keep:
            filename = get_filename(filename)
        else:
            found_file.delete()

    new_file = File(
        file_name=filename,
        content_type=file.content_type,
        owner_id=str(current_user.id),
        owner=current_user.name,
        parent=found_dir
    )
    new_file.file_content.new_file()
    new_file.file_content.write(await file.read())
    new_file.file_content.close()
    new_file.save()

    return new_file


@router.get("/download/{directory}/{filename}")
async def download_file(
    directory: str,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    found_dir = Directory.objects(dir_name=directory, owner_id=str(current_user.id)).first()
    if not found_dir:
        raise HTTPException(status_code=404, detail=f"Dossier '{directory}' introuvable")

    file = File.objects(file_name=filename, parent=found_dir).first()
    if not file:
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable dans '{directory}'")

    return StreamingResponse(
        content=iter_chunks(file.file_content, settings.chunk_size),
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename={file.file_name}"}
    )


@router.get("/list", response_model=List[FileOut])
async def get_files_in_directory(
    current_user: Annotated[User, Depends(get_current_user)],
    directory: str | None = None,
    limit: int = 5,
    skip: int = 0,
):
    if directory:
        found_dir = Directory.objects(dir_name=directory, owner_id=str(current_user.id)).first()
        if not found_dir:
            raise HTTPException(status_code=404, detail=f"Dossier '{directory}' introuvable")
        files = File.objects(parent=found_dir, owner_id=str(current_user.id)).limit(limit).skip(skip)
    else:
        files = File.objects(owner_id=str(current_user.id)).limit(limit).skip(skip)

    return files


@router.delete("/delete/{directory}/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    directory: str,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    found_dir = Directory.objects(dir_name=directory, owner_id=str(current_user.id)).first()
    if not found_dir:
        raise HTTPException(status_code=404, detail=f"Dossier '{directory}' introuvable")

    file = File.objects(file_name=filename, parent=found_dir).first()
    if not file:
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable dans '{directory}'")

    if file.owner_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Non autorisé à supprimer ce fichier")

    file.file_content.delete()
    file.delete()

    return {"detail": "Fichier supprimé avec succès"}


@router.patch("/rename-directory/{current_directory_name}", status_code=status.HTTP_200_OK)
async def rename_directory(
    current_directory_name: str,
    new_directory_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not new_directory_name:
        raise HTTPException(status_code=400, detail="Le nouveau nom du dossier est requis")

    existing_dir = Directory.objects(dir_name=current_directory_name, owner_id=str(current_user.id)).first()
    if not existing_dir:
        raise HTTPException(status_code=404, detail="Le dossier actuel n'existe pas")

    if Directory.objects(dir_name=new_directory_name, owner_id=str(current_user.id)).first():
        raise HTTPException(status_code=409, detail="Un dossier avec ce nom existe déjà")

    existing_dir.dir_name = new_directory_name
    existing_dir.save()

    return {"detail": "Dossier renommé avec succès"}
