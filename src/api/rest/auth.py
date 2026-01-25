from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, status
import asyncpg
from src.auth.jwt import create_access_token, create_refresh_token
from src.auth.schemas import SignupRequest, SignupResponse, LoginRequest, LoginResponse
from src.auth.service import AuthService
from src.config import config
from src.database import get_db
from src.utils import logger

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class TokenManager:
    @staticmethod
    def create_tokens(user_id: str) -> tuple[str, str]:
        jti = str(uuid4())
        access_token = create_access_token(
            data={"sub": user_id, "jti": jti},
            expires_delta=timedelta(minutes=config.jwt_access_token_expire_minutes)
        )
        refresh_token = create_refresh_token(data={"sub": user_id})
        return access_token, refresh_token
    
    @staticmethod
    def get_expires_in() -> int:
        return config.jwt_access_token_expire_minutes * 60

class RequestInfoExtractor:
    @staticmethod
    def get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    @staticmethod
    def get_user_agent(request: Request) -> str:
        return request.headers.get("User-Agent", "unknown")

class AuthController:
    def __init__(self, db: asyncpg.Connection, request: Request):
        self.auth_service = AuthService(db)
        self.token_manager = TokenManager()
        self.request_extractor = RequestInfoExtractor()
        self.request = request
    
    async def _create_authenticated_response(self, user: dict) -> tuple[str, str]:
        access_token, refresh_token = self.token_manager.create_tokens(user["id"])
        ip_address = self.request_extractor.get_client_ip(self.request)
        user_agent = self.request_extractor.get_user_agent(self.request)
        
        await self.auth_service.store_session(
            UUID(user["id"]),
            access_token,
            refresh_token,
            ip_address,
            user_agent
        )
        
        return access_token, refresh_token
    
    async def signup(self, signup_request: SignupRequest) -> SignupResponse:
        user = await self.auth_service.create_user(
            signup_request.email,
            signup_request.password,
            signup_request.name
        )
        
        access_token, refresh_token = await self._create_authenticated_response(user)
        
        logger.info("User signed up successfully", user_id=user["id"])
        
        return SignupResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.token_manager.get_expires_in(),
            user=user
        )
    
    async def login(self, login_request: LoginRequest) -> LoginResponse:
        user = await self.auth_service.authenticate_user(
            login_request.email,
            login_request.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token, refresh_token = await self._create_authenticated_response(user)
        
        logger.info("User logged in successfully", user_id=user["id"])
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.token_manager.get_expires_in()
        )

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    http_request: Request,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        controller = AuthController(db, http_request)
        return await controller.signup(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Signup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: asyncpg.Connection = Depends(get_db)
):
    try:
        controller = AuthController(db, http_request)
        return await controller.login(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
