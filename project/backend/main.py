import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    CurrentUser,
    TokenResponse,
)
from database import init_db
from routers import works, alerts, analytics, roles, meta, upload

app = FastAPI(
    title="MPLADS AI Monitoring Platform",
    description="AI-powered monitoring & analytics platform for MPLADS fund utilization "
                "and project execution — built for Smart India Hackathon (MoSPI).",
    version="1.0.0",
)

# Allowed origins including both standard and trailing-slash variants
origins = [
    "https://ai-based-mplods-analysis.vercel.app",
    "https://ai-based-mplods-analysis.vercel.app/",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "MPLADS AI Monitoring Platform API",
        "docs": "/docs",
    }


@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(
        username=form_data.username, role=user["role"], scope=user["scope"]
    )
    return TokenResponse(
        access_token=token,
        role=user["role"],
        scope=user["scope"],
        display_name=user["display_name"],
    )


@app.get("/auth/me", response_model=CurrentUser)
def read_current_user(user: CurrentUser = Depends(get_current_user)):
    return user


# Router inclusions — each router already defines its own /api/... prefix
# internally (see routers/*.py), so no extra prefix is added here.
# Adding "/api" again here would double it up (e.g. /api/api/roles/...)
# and cause every endpoint to 404.
app.include_router(works.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(roles.router)
app.include_router(meta.router)
app.include_router(upload.router)
