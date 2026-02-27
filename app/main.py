import os
import uuid
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from dotenv import load_dotenv

from app.schemas import TranslationResponse
from app.agents import parse_fountain, translate_screenplay, format_fountain, format_pdf

load_dotenv()

app = FastAPI(title="Screenplay Translator API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pasta temporária para arquivos gerados
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Armazena o progresso de cada sessão em memória
sessions: dict = {}


@app.get("/")
def root():
    return {"status": "backend online"}

@app.get("/debug/{session_id}")
def debug(session_id: str):
    return sessions.get(session_id, {"error": "sessão não encontrada"})

@app.post("/translate", response_model=TranslationResponse)
async def translate(file: UploadFile = File(...)):
    """
    Recebe o arquivo .fountain, inicia o processo de tradução
    e retorna um session_id para acompanhar o progresso via SSE.
    """

    if not file.filename.endswith(".fountain"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .fountain são aceitos.")

    session_id = str(uuid.uuid4())
    raw_text = (await file.read()).decode("utf-8")
    title = file.filename.replace(".fountain", "")

    # Inicializa a sessão
    sessions[session_id] = {
        "stage": "queued",
        "progress": 0,
        "message": "Na fila...",
        "fountain_path": None,
        "pdf_path": None,
        "error": None,
    }

    # Inicia o pipeline em background
    asyncio.create_task(run_pipeline(session_id, raw_text, title))

    return TranslationResponse(
        session_id=session_id,
        status="started",
        message="Tradução iniciada.",
    )


async def run_pipeline(session_id: str, raw_text: str, title: str):
    """
    Executa os três agentes em sequência e atualiza o progresso da sessão.
    """

    def update(stage, progress, message):
        sessions[session_id].update({
            "stage": stage,
            "progress": progress,
            "message": message,
        })

    try:
        # Agente 1 — Parser
        update("parsing", 10, "Analisando o roteiro...")
        loop = asyncio.get_event_loop()
        document = await loop.run_in_executor(None, parse_fountain, raw_text, title)

        # Agente 2 — Tradutor
        update("translating", 40, "Traduzindo para português brasileiro...")
        document = await loop.run_in_executor(None, translate_screenplay, document)

        # Agente 3 — Formatador Fountain
        update("formatting", 70, "Reconstruindo o roteiro em Fountain...")
        fountain_text = await loop.run_in_executor(None, format_fountain, document)

        # Geração do PDF
        update("generating_output", 85, "Gerando PDF...")
        pdf_bytes = await loop.run_in_executor(None, format_pdf, fountain_text, title)

        # Salva os arquivos
        fountain_path = OUTPUT_DIR / f"{session_id}.fountain"
        pdf_path = OUTPUT_DIR / f"{session_id}.pdf"

        fountain_path.write_text(fountain_text, encoding="utf-8")
        pdf_path.write_bytes(pdf_bytes)

        sessions[session_id].update({
            "stage": "done",
            "progress": 100,
            "message": "Tradução concluída!",
            "fountain_path": str(fountain_path),
            "pdf_path": str(pdf_path),
        })

    except Exception as e:
        sessions[session_id].update({
            "stage": "error",
            "progress": 0,
            "message": "Erro durante a tradução.",
            "error": str(e),
        })


@app.get("/progress/{session_id}")
async def progress(session_id: str):
    """
    Endpoint SSE — o frontend se conecta aqui para receber
    eventos de progresso em tempo real.
    """

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    async def event_stream():
        last_stage = None
        while True:
            session = sessions.get(session_id)
            if not session:
                break

            current_stage = session["stage"]

            # Só envia evento se houver mudança de estágio
            if current_stage != last_stage:
                data = (
                    f"data: {{"
                    f'"stage": "{session["stage"]}", '
                    f'"progress": {session["progress"]}, '
                    f'"message": "{session["message"]}"'
                    f"}}\n\n"
                )
                yield data
                last_stage = current_stage

            if current_stage in ("done", "error"):
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/download/{session_id}/{format}")
async def download(session_id: str, format: str):
    """
    Endpoint de download do arquivo traduzido.
    format: "fountain" ou "pdf"
    """

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    session = sessions[session_id]

    if session["stage"] != "done":
        raise HTTPException(status_code=400, detail="Tradução ainda não concluída.")

    if format == "fountain":
        path = session["fountain_path"]
        media_type = "text/plain"
        filename = f"roteiro_traduzido.fountain"
    elif format == "pdf":
        path = session["pdf_path"]
        media_type = "application/pdf"
        filename = f"roteiro_traduzido.pdf"
    else:
        raise HTTPException(status_code=400, detail="Formato inválido. Use 'fountain' ou 'pdf'.")

    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    return FileResponse(path, media_type=media_type, filename=filename)