import uuid
from typing import Sequence
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.deps import get_db
from app.schemas.client import (
    ClientBrandKitRead,
    ClientBrandKitUpdate,
    ClientDetailRead,
    ClientPersonaRead,
    ClientPersonaUpdate,
    ClientProfileCreate,
    ClientProfileRead,
    ClientTopicFilterRead,
    ClientTopicFilterUpdate,
)
from app.services.client_service import ClientService

router = APIRouter()


@router.post("/", response_model=ClientDetailRead, status_code=status.HTTP_201_CREATED)
def create_client_profile(
    payload: ClientProfileCreate,
    session: Session = Depends(get_db),
) -> ClientDetailRead:
    service = ClientService(session)
    return service.create_client(payload)


@router.get("/", response_model=list[ClientProfileRead])
def list_client_profiles(
    session: Session = Depends(get_db),
) -> Sequence[ClientProfileRead]:
    service = ClientService(session)
    return service.list_clients()


@router.get("/{client_id}", response_model=ClientDetailRead)
def get_client_profile(
    client_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ClientDetailRead:
    service = ClientService(session)
    detail = service.get_client_detail(client_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found.",
        )
    return detail


@router.put("/{client_id}/persona", response_model=ClientPersonaRead)
def update_client_persona(
    client_id: uuid.UUID,
    payload: ClientPersonaUpdate,
    session: Session = Depends(get_db),
) -> ClientPersonaRead:
    service = ClientService(session)
    updated = service.update_persona(client_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found.",
        )
    return updated


@router.put("/{client_id}/topics", response_model=ClientTopicFilterRead)
def update_client_topic_filter(
    client_id: uuid.UUID,
    payload: ClientTopicFilterUpdate,
    session: Session = Depends(get_db),
) -> ClientTopicFilterRead:
    service = ClientService(session)
    updated = service.update_topic_filter(client_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found.",
        )
    return updated


@router.put("/{client_id}/brand-kit", response_model=ClientBrandKitRead)
def update_client_brand_kit(
    client_id: uuid.UUID,
    payload: ClientBrandKitUpdate,
    session: Session = Depends(get_db),
) -> ClientBrandKitRead:
    service = ClientService(session)
    updated = service.update_brand_kit(client_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found.",
        )
    return updated
