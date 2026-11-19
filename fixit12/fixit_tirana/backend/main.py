import hashlib
import hmac
import os
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
load_dotenv(BASE_DIR / ".env")

from backend.database import (
    add_chat_message,
    clear_chat_history,
    create_report,
    get_chat_history,
    get_report,
    init_db,
    list_recommendations,
    list_reports,
    save_ai_analysis,
    save_recommendation,
    update_report_status,
)
from backend.ai_assistant import (
    GEMINI_MODEL,
    analyze_report,
    answer_admin_question,
    suggest_solutions,
)

app = FastAPI(title="FixIt Tirana", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "development-secret-change-me"),
    session_cookie="fixit_session",
    same_site="lax",
    https_only=os.getenv("COOKIE_HTTPS_ONLY", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/styles.css")
async def styles_css():
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@app.get("/public.js")
async def public_js():
    return FileResponse(FRONTEND_DIR / "public.js", media_type="application/javascript")


@app.get("/admin.js")
async def admin_js():
    return FileResponse(FRONTEND_DIR / "admin.js", media_type="application/javascript")


@app.on_event("startup")
def startup():
    init_db()


def is_admin(request: Request) -> bool:
    return request.session.get("is_admin") is True


def admin_required(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(
            status_code=401,
            detail="Duhet të identifikohesh si administrator.",
        )


def page(name: str) -> str:
    return (FRONTEND_DIR / name).read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def public_home():
    return page("index.html")


@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    return page("login.html")


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    expected_user = os.getenv("ADMIN_USERNAME", "admin").strip()
    stored_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()

    valid_password = False
    if "$" in stored_hash:
        salt, expected_digest = stored_hash.split("$", 1)
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            310_000,
        ).hex()
        valid_password = hmac.compare_digest(candidate_digest, expected_digest)
    else:
        # Backward compatibility for projects configured with a plain password.
        # Prefer ADMIN_PASSWORD_HASH, created with backend/create_admin.py.
        legacy_password = os.getenv("ADMIN_PASSWORD", "")
        valid_password = bool(legacy_password) and hmac.compare_digest(
            password, legacy_password
        )

    valid_user = hmac.compare_digest(username.strip(), expected_user)
    if valid_user and valid_password:
        request.session.clear()
        request.session["is_admin"] = True
        request.session["session_id"] = str(uuid.uuid4())
        return RedirectResponse("/admin", status_code=303)

    request.session.clear()
    return RedirectResponse("/login.html?error=1", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not is_admin(request):
        return RedirectResponse("/login.html", status_code=303)
    return page("admin.html")


@app.post("/api/reports")
async def submit_report(
    category: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    photo: Optional[UploadFile] = File(None),
):
    category = category.strip()
    description = description.strip()
    location = location.strip()
    if category not in {
        "Rrugë dhe trotuare", "Ndriçim publik", "Ujë dhe kanalizime",
        "Mbetje dhe pastërti", "Hapësira publike", "Sinjalistikë dhe trafik",
        "Tjetër",
    }:
        raise HTTPException(status_code=400, detail="Kategoria nuk është e vlefshme.")
    if not description or len(description) > 3000 or not location or len(location) > 250:
        raise HTTPException(
            status_code=400,
            detail="Kontrollo përshkrimin dhe vendndodhjen.",
        )

    photo_name = None
    if photo and photo.filename:
        suffix = Path(photo.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(
                status_code=400,
                detail="Fotoja duhet të jetë JPG, PNG ose WEBP.",
            )
        content = await photo.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Fotoja nuk duhet të kalojë 5 MB.",
            )
        photo_name = f"{uuid.uuid4().hex}{suffix}"
        (UPLOAD_DIR / photo_name).write_bytes(content)

    report_id = create_report(category, description, location, photo_name)
    return JSONResponse({
        "ok": True,
        "id": report_id,
        "message": "Raportimi u ruajt në platformë.",
    })


@app.get("/api/reports")
async def reports_api(
    request: Request,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    admin_required(request)
    return {"reports": list_reports(status, search)}


@app.get("/api/reports/{report_id}")
async def report_detail(request: Request, report_id: int):
    admin_required(request)
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Raportimi nuk u gjet.")
    return report


@app.patch("/api/reports/{report_id}/status")
async def report_status(request: Request, report_id: int, payload: dict):
    admin_required(request)
    status = payload.get("status")
    if status not in {"E re", "Në shqyrtim", "Në proces", "E zgjidhur"}:
        raise HTTPException(status_code=400, detail="Status i pavlefshëm.")
    if not update_report_status(report_id, status):
        raise HTTPException(status_code=404, detail="Raportimi nuk u gjet.")
    return {"ok": True}


def _get_report_id(payload: dict) -> int:
    try:
        return int(payload.get("report_id"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Zgjidh një raportim të vlefshëm.",
        ) from None


@app.post("/api/ai/analyze-report")
async def ai_analyze(request: Request, payload: dict):
    admin_required(request)
    report = get_report(_get_report_id(payload))
    if not report:
        raise HTTPException(status_code=404, detail="Raportimi nuk u gjet.")
    try:
        result = await analyze_report(report)
        save_ai_analysis(report["id"], result["summary"], result["priority"])
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Asistenti AI nuk mundi të përgjigjej: {exc}",
        ) from exc


@app.post("/api/ai/suggest-solutions")
async def ai_suggest_solutions(request: Request, payload: dict):
    admin_required(request)
    category = str(payload.get("category", "")).strip()
    location = str(payload.get("location", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not category or not description or len(description) > 3000 or len(location) > 250:
        raise HTTPException(status_code=400, detail="Raportimi nuk është i vlefshëm.")
    try:
        return await suggest_solutions(category, location, description)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Asistenti AI nuk mundi të përgjigjej: {exc}",
        ) from exc


@app.post("/api/ai/chat")
async def ai_chat(request: Request, payload: dict):
    admin_required(request)
    question = str(payload.get("message", "")).strip()
    if not question or len(question) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Shkruaj një pyetje deri në 2000 karaktere.",
        )

    report = None
    if payload.get("report_id"):
        try:
            report = get_report(int(payload["report_id"]))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Raportimi nuk është i vlefshëm.") from None
        if not report:
            raise HTTPException(status_code=404, detail="Raportimi nuk u gjet.")

    session_id = request.session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["session_id"] = session_id

    history = get_chat_history(session_id)
    try:
        answer = await answer_admin_question(question, history, report)
        add_chat_message(session_id, "user", question)
        add_chat_message(session_id, "assistant", answer)
        return {"answer": answer}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Asistenti AI nuk mundi të përgjigjej: {exc}",
        ) from exc


@app.delete("/api/ai/chat")
async def clear_chat(request: Request):
    admin_required(request)
    session_id = request.session.get("session_id")
    if session_id:
        clear_chat_history(session_id)
    return {"ok": True}


@app.post("/api/recommendations")
async def recommendation_save(request: Request, payload: dict):
    admin_required(request)
    content = str(payload.get("content", "")).strip()
    report_id = payload.get("report_id")
    if not content:
        raise HTTPException(status_code=400, detail="Rekomandimi është bosh.")
    if report_id:
        try:
            report_id = int(report_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Raportimi nuk është i vlefshëm.") from None
        if not get_report(report_id):
            raise HTTPException(status_code=404, detail="Raportimi nuk u gjet.")
    save_recommendation(report_id, content)
    return {"ok": True}


@app.get("/api/recommendations")
async def recommendations_api(request: Request):
    admin_required(request)
    return {"recommendations": list_recommendations()}


@app.get("/api/health")
async def health():
    configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "status": "ok",
        "ai_provider": "Google Gemini",
        "ai_available": configured,
        "model": GEMINI_MODEL,
    }
