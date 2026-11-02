from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_db
from app.schemas import UserCreate, TokenOut
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.config import settings
from app.utils import now_utc, serialize_doc

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    db = get_db()
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = {
        "email": email,
        "full_name": payload.full_name.strip(),
        "password_hash": hash_password(payload.password),
        "created_at": now_utc(),
    }
    result = await db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return {"user": {"id": str(user["_id"]), "email": user["email"], "full_name": user["full_name"], "created_at": user["created_at"].isoformat()}}

@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = await get_db().users.find_one({"email": form.username.lower()})
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(str(user["_id"]))
    return TokenOut(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"id": str(user["_id"]), "email": user["email"], "full_name": user["full_name"], "created_at": user["created_at"].isoformat()}
