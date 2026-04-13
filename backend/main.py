"""
main.py
-------
FastAPI uygulamasının giriş noktası.

Başlatmak için:
    cd smart-flashcard/backend
    uvicorn main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from config import settings
from database import create_tables

# Router'ları içe aktar
from routers.documents  import router as documents_router
from routers.flashcards import router as flashcards_router
from routers.tags       import router as tags_router
from routers.quiz       import router as quiz_router
from routers.export     import router as export_router


# ── Uygulama Yaşam Döngüsü ────────────────────────────────────────────────────
from tasks.cleanup import start_cleanup_worker
from database import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sunucu başlarken tabloları oluştur, temizlik görevini başlat."""
    print("🚀 Smart Flashcard API başlatılıyor...")
    create_tables()                          # SQLite tablolarını oluştur
    
    if settings.AUTO_CLEANUP_ENABLED:
        start_cleanup_worker()                # Arka plan temizlik görevini başlat
        print(f"🧹 Otomatik temizlik aktif ({settings.AUTO_CLEANUP_HOURS} saat).")
        
    yield
    print("🛑 Sunucu kapatıldı.")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "PDF, DOCX veya metin girdisinden otomatik olarak "
        "akıllı flashcard üreten REST API."
    ),
    docs_url="/docs",         # Swagger UI
    redoc_url="/redoc",       # ReDoc
    lifespan=lifespan,
)



# ── CORS Middleware ───────────────────────────────────────────────────────────
# Frontend (localhost:5500 vb.) ile aynı makineden erişim için
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Router Kaydı ─────────────────────────────────────────────────────────────
app.include_router(documents_router,  prefix="/api", tags=["Dokümanlar"])
app.include_router(flashcards_router, prefix="/api", tags=["Flashcard'lar"])
app.include_router(tags_router,       prefix="/api", tags=["Etiketler"])
app.include_router(quiz_router,       prefix="/api", tags=["Quiz (Sınav)"])
app.include_router(export_router,     prefix="/api", tags=["Dışa Aktar"])


# ── Statik Dosyalar (Frontend) ────────────────────────────────────────────────
# Frontend klasörü varsa tüm static asset'leri sun
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # /static/* -> frontend/css, js, img vs.
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Ana sayfayı (frontend/index.html) göster."""
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse({"message": "Frontend henüz oluşturulmadı."})
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }


# ── Sağlık Kontrolü ───────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistem"])
async def health_check():
    """Sunucunun çalışıp çalışmadığını döndürür."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ── Global Hata Yakalayıcı ────────────────────────────────────────────────────
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Doğrulama hatası", "errors": errors},
    )
