from fastapi import APIRouter, Depends, HTTPException

from routers.auth import get_current_user
from services import iflytek_iat_service

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/iflytek/status")
def get_iflytek_status(_user=Depends(get_current_user)):
    return iflytek_iat_service.get_iflytek_public_config()


@router.get("/iflytek/ws-url")
def get_iflytek_ws_url(_user=Depends(get_current_user)):
    try:
        return {"url": iflytek_iat_service.build_iat_ws_url()}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
