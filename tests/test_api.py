import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"   # separate DB for tests

from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def make_patient():
    return client.post("/patients", json={"name": "Asha", "age": 30, "phone": "9999999999"}).json()


def make_doctor():
    return client.post("/doctors", json={"name": "Dr. Rao", "specialization": "Cardiology"}).json()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_create_and_get_patient():
    p = make_patient()
    assert client.get(f"/patients/{p['id']}").json()["name"] == "Asha"


def test_invalid_patient_rejected():
    r = client.post("/patients", json={"name": "X", "age": -5, "phone": "123456"})
    assert r.status_code == 422


def test_create_doctor_and_list():
    make_doctor()
    assert len(client.get("/doctors").json()) == 1


def test_book_appointment():
    p, d = make_patient(), make_doctor()
    r = client.post("/appointments", json={
        "patient_id": p["id"], "doctor_id": d["id"],
        "scheduled_at": "2026-12-01T10:00:00", "reason": "Checkup"})
    assert r.status_code == 201


def test_double_booking_blocked():
    p, d = make_patient(), make_doctor()
    body = {"patient_id": p["id"], "doctor_id": d["id"], "scheduled_at": "2026-12-01T10:00:00"}
    assert client.post("/appointments", json=body).status_code == 201
    assert client.post("/appointments", json=body).status_code == 409


def test_appointment_unknown_patient():
    d = make_doctor()
    r = client.post("/appointments", json={
        "patient_id": 999, "doctor_id": d["id"], "scheduled_at": "2026-12-01T10:00:00"})
    assert r.status_code == 404


def test_metrics_endpoint():
    client.get("/patients")
    assert "http_requests_total" in client.get("/metrics").text


def test_home_page():
    r = client.get("/")
    assert r.status_code == 200 and "Hospital Management System" in r.text
