import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

import auth_store
import google_oauth
import google_sync
import Planner
import privacy
import workspace
import ingest
from supabase_client import get_client

app = FastAPI(title="Insight Agent API", version="1.0.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_MAX_AGE = 60 * 60 * 24 * 30
OAUTH_VERIFIER_COOKIE = "pi_agent_oauth_verifier"
OAUTH_VERIFIER_MAX_AGE = 600

SESSION_SECRET = os.getenv("SECRET_KEY")
if not SESSION_SECRET:
    raise ValueError("SECRET_KEY is not set.")

serializer = URLSafeTimedSerializer(SESSION_SECRET)


def create_token(user_id):
    return serializer.dumps({"user_id": user_id})


def read_token(value):
    if not value:
        return None
    try:
        data = serializer.loads(value, max_age=SESSION_MAX_AGE)
        return data.get("user_id")
    except BadSignature:
        return None


def get_current_user_id_optional(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return read_token(auth[7:])
    return None


def get_current_user_id(request: Request):
    user_id = get_current_user_id_optional(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return user_id


class ChatRequest(BaseModel):
    question: str


class WorkspaceRequest(BaseModel):
    folder: str


class DrivePickedFile(BaseModel):
    id: str
    name: str
    mimeType: str


class DriveSyncRequest(BaseModel):
    files: list[DrivePickedFile]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/auth/google/login")
def google_login():
    auth_url, _state, code_verifier = google_oauth.get_authorization_url()
    response = RedirectResponse(auth_url)
    response.set_cookie(
        OAUTH_VERIFIER_COOKIE,
        serializer.dumps({"code_verifier": code_verifier}),
        httponly=True, secure=True, samesite="none",
        max_age=OAUTH_VERIFIER_MAX_AGE,
    )
    return response


@app.get("/auth/google/callback")
def google_callback(code: str, request: Request):
    verifier_cookie = request.cookies.get(OAUTH_VERIFIER_COOKIE)
    try:
        payload = serializer.loads(verifier_cookie, max_age=OAUTH_VERIFIER_MAX_AGE)
        code_verifier = payload.get("code_verifier")
    except (BadSignature, TypeError):
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=session_expired")

    try:
        credentials = google_oauth.exchange_code(code, code_verifier)
        user_info = google_oauth.get_user_info(credentials)
    except Exception as e:
        print(f"[auth] OAuth exchange failed: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}/?error=oauth_failed")

    # ↓ continue with the rest of your existing code from here ↓
    user_id = user_info["sub"]
    email = user_info.get("email", "unknown")

    if not credentials.refresh_token:
        raise HTTPException(status_code=500, detail="No refresh token from Google.")

    auth_store.save_user(user_id, email, credentials.refresh_token)

    try:
        supabase = get_client()
        supabase.table("users").upsert({
            "email": email,
            "google_sub": user_id,
            "collection_name": google_sync.collection_name_for(user_id),
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="google_sub").execute()
    except Exception as error:
        print(f"[auth] failed to upsert user record for {email}: {error}")

    token = create_token(user_id)
    response = RedirectResponse(url=f"{FRONTEND_URL}/app/chat?token={token}")
    response.delete_cookie(OAUTH_VERIFIER_COOKIE, httponly=True, secure=True, samesite="none")
    return response


@app.get("/auth/me")
def auth_me(user_id: str = Depends(get_current_user_id_optional)):
    if not user_id:
        return {"logged_in": False}
    user = auth_store.get_user(user_id)
    return {"logged_in": True, "email": user["email"] if user else None}


@app.post("/auth/logout")
def logout():
    return JSONResponse({"success": True})


@app.post("/sync/calendar")
def sync_calendar_endpoint(user_id: str = Depends(get_current_user_id)):
    user = auth_store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Google account not connected.")
    credentials = google_oauth.credentials_from_refresh_token(user["refresh_token"])
    return google_sync.sync_calendar(user_id, credentials)


@app.get("/auth/google/picker-token")
def picker_token(user_id: str = Depends(get_current_user_id)):
    user = auth_store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Google account not connected.")
    developer_key = os.getenv("GOOGLE_PICKER_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    app_id = os.getenv("GOOGLE_APP_ID")
    if not developer_key or not app_id:
        raise HTTPException(status_code=500, detail="Picker not configured.")
    credentials = google_oauth.credentials_from_refresh_token(user["refresh_token"])
    return {
        "access_token": credentials.token,
        "developer_key": developer_key,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "app_id": app_id,
    }


@app.post("/sync/drive")
def sync_drive_endpoint(request: DriveSyncRequest, user_id: str = Depends(get_current_user_id)):
    user = auth_store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Google account not connected.")
    credentials = google_oauth.credentials_from_refresh_token(user["refresh_token"])
    picked_files = [f.dict() for f in request.files]
    return google_sync.sync_drive_files(user_id, credentials, picked_files)


@app.post("/chat")
def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id_optional)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    collection_name = google_sync.collection_name_for(user_id) if user_id else None
    result = Planner.answer_with_planner(request.question, collection_name=collection_name)
    return {
        "answer": result["answer"],
        "route": result["route"],
        "confidence_tier": result["confidence_tier"],
        "chart": result.get("chart"),
    }


@app.get("/data/tabular")
def list_tabular_files(user_id: str = Depends(get_current_user_id_optional)):
    collection_name = google_sync.collection_name_for(user_id) if user_id else ingest.COLLECTION_NAME
    client = get_client()
    response = client.table("structured_rows").select("filename, sheet_name").eq("collection_name", collection_name).execute()
    seen, files = set(), []
    for row in response.data or []:
        key = (row["filename"], row.get("sheet_name"))
        if key not in seen:
            seen.add(key)
            files.append({"filename": row["filename"], "sheet_name": row.get("sheet_name")})
    return {"files": files}


@app.get("/data/tabular/{filename}")
def get_tabular_data(filename: str, sheet_name: str = None, user_id: str = Depends(get_current_user_id_optional)):
    collection_name = google_sync.collection_name_for(user_id) if user_id else ingest.COLLECTION_NAME
    client = get_client()
    query = client.table("structured_rows").select("row_index, row_data, sheet_name").eq("collection_name", collection_name).eq("filename", filename)
    if sheet_name:
        query = query.eq("sheet_name", sheet_name)
    response = query.order("row_index").execute()
    if not response.data:
        raise HTTPException(status_code=404, detail=f"No data for '{filename}'.")
    return {"filename": filename, "sheet_name": sheet_name, "rows": [r["row_data"] for r in response.data]}


@app.get("/workspaces")
def get_workspaces():
    return {"folders": workspace.load_workspaces()}


@app.post("/workspaces")
def add_workspace(request: WorkspaceRequest):
    success, message = workspace.add_workspace(request.folder)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "folders": workspace.load_workspaces()}


@app.delete("/workspaces")
def remove_workspace(request: WorkspaceRequest):
    success, message = workspace.remove_workspace(request.folder)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "folders": workspace.load_workspaces()}


@app.post("/ingest")
def run_ingest():
    try:
        ingest.ingest_files()
        return {"success": True, "message": "Ingestion complete."}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/privacy/inventory")
def privacy_inventory(user_id: str = Depends(get_current_user_id_optional)):
    collection_name = google_sync.collection_name_for(user_id) if user_id else None
    return privacy.get_data_inventory(collection_name=collection_name)


@app.post("/privacy/purge")
def purge_privacy_data(user_id: str = Depends(get_current_user_id_optional)):
    collection_name = google_sync.collection_name_for(user_id) if user_id else None
    return privacy.purge_all_local_data(confirm=True, collection_name=collection_name)