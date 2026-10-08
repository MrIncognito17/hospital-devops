import json
import logging
import os
import sys
import time
from typing import List

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

APP_VERSION = os.getenv("APP_VERSION", "dev")


# ---------- Logging: JSON lines to stdout (what log collectors expect) ----------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "hospital-api",
            "version": APP_VERSION,
        })


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("hospital")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
logger.handlers = [handler]

# ---------- Metrics for Prometheus ----------
REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["path"])

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Hospital Management System", version=APP_VERSION)


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    path = request.url.path
    if path not in ("/metrics", "/health"):
        REQUESTS.labels(request.method, path, response.status_code).inc()
        LATENCY.labels(path).observe(duration)
        logger.info(f"{request.method} {path} -> {response.status_code} ({duration*1000:.1f} ms)")
    return response


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------- Patients ----------
@app.post("/patients", response_model=schemas.PatientOut, status_code=201)
def create_patient(data: schemas.PatientIn, db: Session = Depends(get_db)):
    obj = models.Patient(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@app.get("/patients", response_model=List[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(models.Patient).all()


@app.get("/patients/{pid}", response_model=schemas.PatientOut)
def get_patient(pid: int, db: Session = Depends(get_db)):
    obj = db.get(models.Patient, pid)
    if not obj:
        raise HTTPException(404, "Patient not found")
    return obj


@app.delete("/patients/{pid}", status_code=204)
def delete_patient(pid: int, db: Session = Depends(get_db)):
    obj = db.get(models.Patient, pid)
    if not obj:
        raise HTTPException(404, "Patient not found")
    db.delete(obj); db.commit()


# ---------- Doctors ----------
@app.post("/doctors", response_model=schemas.DoctorOut, status_code=201)
def create_doctor(data: schemas.DoctorIn, db: Session = Depends(get_db)):
    obj = models.Doctor(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@app.get("/doctors", response_model=List[schemas.DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    return db.query(models.Doctor).all()


@app.get("/doctors/{did}", response_model=schemas.DoctorOut)
def get_doctor(did: int, db: Session = Depends(get_db)):
    obj = db.get(models.Doctor, did)
    if not obj:
        raise HTTPException(404, "Doctor not found")
    return obj


# ---------- Appointments ----------
@app.post("/appointments", response_model=schemas.AppointmentOut, status_code=201)
def create_appointment(data: schemas.AppointmentIn, db: Session = Depends(get_db)):
    if not db.get(models.Patient, data.patient_id):
        raise HTTPException(404, "Patient not found")
    if not db.get(models.Doctor, data.doctor_id):
        raise HTTPException(404, "Doctor not found")
    clash = db.query(models.Appointment).filter_by(
        doctor_id=data.doctor_id, scheduled_at=data.scheduled_at).first()
    if clash:
        raise HTTPException(409, "Doctor already booked at that time")
    obj = models.Appointment(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@app.get("/appointments", response_model=List[schemas.AppointmentOut])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(models.Appointment).all()


@app.delete("/appointments/{aid}", status_code=204)
def cancel_appointment(aid: int, db: Session = Depends(get_db)):
    obj = db.get(models.Appointment, aid)
    if not obj:
        raise HTTPException(404, "Appointment not found")
    db.delete(obj); db.commit()
