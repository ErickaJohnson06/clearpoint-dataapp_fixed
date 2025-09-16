from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import io, json, fitz
from PIL import Image, ImageDraw

app = FastAPI(title="ClearPoint — Redactor Pro")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def ui(request: Request):
    return templates.TemplateResponse("redactor_pro.html", {"request": request})

# Preview first 5 pages of a PDF
@app.post("/api/preview_pdf")
async def preview_pdf(file: UploadFile = File(...)):
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    images = []
    for i in range(min(5, len(doc))):
        pix = doc.load_page(i).get_pixmap(dpi=144)
        images.append(pix.tobytes("png"))
    import base64
    b64s = [base64.b64encode(im).decode("ascii") for im in images]
    return {"pages": b64s}

# Apply redactions to PDF
@app.post("/api/redact_pdf")
async def redact_pdf(file: UploadFile = File(...), rects_json: str = Form("[]")):
    rects = json.loads(rects_json)
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    scale = 72/144
    for r in rects:
        page = doc.load_page(int(r["page"]))
        rect = fitz.Rect(r["x"]*scale, r["y"]*scale, (r["x"]+r["w"])*scale, (r["y"]+r["h"])*scale)
        page.add_redact_annot(rect, fill=(0,0,0))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
    out = io.BytesIO()
    doc.save(out)
    return StreamingResponse(io.BytesIO(out.getvalue()), media_type="application/pdf",
        headers={"Content-Disposition":"attachment; filename=redacted.pdf"})

# Redact images with solid black boxes
@app.post("/api/redact_image")
async def redact_image(file: UploadFile = File(...), rects_json: str = Form("[]")):
    rects = json.loads(rects_json)
    im = Image.open(io.BytesIO(await file.read())).convert("RGB")
    draw = ImageDraw.Draw(im)
    for r in rects:
        x,y,w,h = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
        draw.rectangle((x,y,x+w,y+h), fill=(0,0,0))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return StreamingResponse(io.BytesIO(out.getvalue()), media_type="image/png",
        headers={"Content-Disposition":"attachment; filename=redacted.png"})

@app.get("/healthz")
def health():
    return {"ok": True}
