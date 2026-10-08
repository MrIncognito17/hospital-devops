from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PatientIn(BaseModel):
    name: str = Field(min_length=1)
    age: int = Field(ge=0, le=150)
    phone: str = Field(min_length=5)


class PatientOut(PatientIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DoctorIn(BaseModel):
    name: str = Field(min_length=1)
    specialization: str = Field(min_length=1)


class DoctorOut(DoctorIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AppointmentIn(BaseModel):
    patient_id: int
    doctor_id: int
    scheduled_at: datetime
    reason: str = ""


class AppointmentOut(AppointmentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
