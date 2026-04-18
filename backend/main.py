import os
import httpx
import asyncio
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from typing import Optional
import time

FAL_KEY_ENV = os.getenv("FAL_KEY", "")
FAL_API_BASE = "https://queue.fal.run"
FAL_ENDPOINT = "fal-ai/wan/v2.2-14b/animate/move"

jobs: dict = {}
job_keys: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Wan Animate Move", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


async def upload_file_to_fal(file_bytes: bytes, filename: str, content_type: str, fal_key: str) -> str:
    """Upload file to fal.ai storage using the correct storage API"""
    async with httpx.AsyncClient(timeout=180) as client:
        # Step 1: initiate upload - get presigned URL
        init_resp = await client.post(
            "https://storage.fal.ai/upload",
            headers={
                "Authorization": f"Key {fal_key}",
                "Content-Type": "application/json",
            },
            json={"content_type": content_type, "file_name": filename},
        )
        if init_resp.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"Upload init failed ({init_resp.status_code}): {init_resp.text[:300]}")
        
        init_data = init_resp.json()
        upload_url = init_data.get("upload_url")
        file_url = init_data.get("file_url")
        
        if not upload_url:
            raise HTTPException(status_code=500, detail=f"No upload_url in response: {init_data}")
        
        # Step 2: PUT file to presigned URL
        put_resp = await client.put(
            upload_url,
            content=file_bytes,
            headers={"Content-Type": content_type},
        )
        if put_resp.status_code not in (200, 201, 204):
            raise HTTPException(status_code=500, detail=f"File PUT failed ({put_resp.status_code}): {put_resp.text[:200]}")
        
        return file_url


async def poll_fal_job(job_id: str, request_id: str):
    fal_key = job_keys.get(job_id, FAL_KEY_ENV)
    elapsed = 0
    interval = 5
    max_wait = 600

    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                sr = await client.get(
                    f"https://queue.fal.run/{FAL_ENDPOINT}/requests/{request_id}/status",
                    headers={"Authorization": f"Key {fal_key}"},
                    params={"logs": "1"},
                )
                if sr.status_code != 200 or not sr.text.strip():
                    jobs[job_id]["logs"] = jobs[job_id].get("logs", []) + [f"Waiting... (HTTP {sr.status_code})"]
                    continue
                sd = sr.json()
                status = sd.get("status", "")
                logs = [
                    (l.get("message", "") if isinstance(l, dict) else str(l))
                    for l in sd.get("logs", [])
                    if (l.get("message", "") if isinstance(l, dict) else str(l))
                ]
                jobs[job_id]["logs"] = logs
                jobs[job_id]["raw_status"] = status

                if status == "COMPLETED":
                    rr = await client.get(
                        f"https://queue.fal.run/{FAL_ENDPOINT}/requests/{request_id}",
                        headers={"Authorization": f"Key {fal_key}"},
                    )
                    result = rr.json()
                    video_url = None
                    if "video" in result:
                        video_url = result["video"].get("url")
                    elif "output" in result and isinstance(result["output"], dict):
                        video_url = result["output"].get("video", {}).get("url")
                    jobs[job_id].update({"status": "completed", "result_url": video_url})
                    return
                elif status in ("FAILED", "CANCELLED"):
                    jobs[job_id].update({"status": "failed", "error": str(sd.get("error", "Job failed"))})
                    return
                else:
                    jobs[job_id]["status"] = "in_progress"
            except Exception as e:
                jobs[job_id]["logs"] = jobs[job_id].get("logs", []) + [f"Poll error: {e}"]

    jobs[job_id].update({"status": "failed", "error": "Timeout after 10 minutes"})


@app.get("/")
async def root():
    index = os.path.join(frontend_path, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "Wan Animate Move API running"}


@app.get("/health")
async def health():
    return {"status": "ok", "fal_key_env_set": bool(FAL_KEY_ENV)}


@app.post("/api/animate")
async def animate(
    request: Request,
    background_tasks: BackgroundTasks,
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    resolution: str = Form("720p"),
    num_inference_steps: int = Form(30),
):
    fal_key = request.headers.get("x-fal-key") or FAL_KEY_ENV
    if not fal_key:
        raise HTTPException(status_code=400, detail="FAL API key required — enter it in the UI or set FAL_KEY env var")

    final_image_url = image_url
    if image_file and image_file.filename:
        img_bytes = await image_file.read()
        final_image_url = await upload_file_to_fal(img_bytes, image_file.filename, image_file.content_type or "image/jpeg", fal_key)

    final_video_url = video_url
    if video_file and video_file.filename:
        vid_bytes = await video_file.read()
        final_video_url = await upload_file_to_fal(vid_bytes, video_file.filename, video_file.content_type or "video/mp4", fal_key)

    if not final_image_url or not final_video_url:
        raise HTTPException(status_code=400, detail="Both image and video are required")

    payload = {
        "image_url": final_image_url,
        "video_url": final_video_url,
        "resolution": resolution,
        "num_inference_steps": num_inference_steps,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        sub = await client.post(
            f"https://queue.fal.run/{FAL_ENDPOINT}",
            headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if sub.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"fal.ai error: {sub.text[:400]}")
        sub_data = sub.json()
        request_id = sub_data.get("request_id")
        if not request_id:
            raise HTTPException(status_code=500, detail=f"No request_id: {sub_data}")

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "job_id": job_id,
        "request_id": request_id,
        "status": "queued",
        "logs": [],
        "raw_status": "QUEUED",
        "result_url": None,
        "error": None,
        "created_at": time.time(),
    }
    job_keys[job_id] = fal_key
    background_tasks.add_task(poll_fal_job, job_id, request_id)

    return {"job_id": job_id, "request_id": request_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs")
async def list_jobs():
    return sorted(jobs.values(), key=lambda j: j.get("created_at", 0), reverse=True)
