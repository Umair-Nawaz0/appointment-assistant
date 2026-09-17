from __future__ import annotations

import re
from datetime import datetime, time
from enum import StrEnum
from typing import Any
from uuid import UUID

from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class AppointmentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    WAITING_BUSINESS = "WAITING_BUSINESS"
    CLOSED = "CLOSED"


class DayOfWeek(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class PasswordMixin:
    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not 10 <= len(value) <= 128 or not re.search(r"[a-z]", value) or not re.search(r"[A-Z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must have at least 10 characters with upper, lower, and a number.")
        return value


class Signup(ApiModel, PasswordMixin):
    businessName: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    industry: str | None = Field(default=None, max_length=120)

    @field_validator("industry", mode="before")
    @classmethod
    def empty_industry_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, value: str) -> str:
        value = value.strip()
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError(f"Invalid timezone '{value}'. Use an IANA timezone such as Asia/Karachi or UTC.")
        return value


class Login(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailInput(ApiModel):
    email: EmailStr


class CodeInput(ApiModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class ResetPassword(ApiModel, PasswordMixin):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    password: str


class BusinessUpdate(ApiModel):
    name: str = Field(min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, max_length=250)
    stateProvince: str | None = Field(default=None, max_length=250)
    postalCode: str | None = Field(default=None, max_length=250)
    countryCode: str | None = Field(default=None, max_length=2)
    industry: str | None = Field(default=None, max_length=250)
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator("address", "city", "stateProvince", "postalCode", "countryCode", "industry", mode="before")
    @classmethod
    def empty_strings_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("countryCode")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        if not value:
            return None
        val = value.strip().upper()
        if len(val) != 2:
            raise ValueError("Country code must be a 2-letter ISO code (e.g. PK, US).")
        return val

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, value: str) -> str:
        value = value.strip()
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError(f"Invalid timezone '{value}'. Use an IANA timezone such as Asia/Karachi or UTC.")
        return value


class SettingsUpdate(ApiModel):
    appointmentDurationMinutes: int = Field(ge=1, le=1440)
    bookingWindowDays: int = Field(ge=1, le=3650)
    maximumAppointmentsPerDay: int | None = Field(default=None, gt=0)
    allowCancellation: bool = True
    allowReschedule: bool = True
    collectPhone: bool = True
    collectEmail: bool = False
    confirmationRequired: bool = False

    @field_validator("maximumAppointmentsPerDay", mode="before")
    @classmethod
    def empty_max_to_none(cls, value: Any) -> int | None:
        if value is None or value == "" or value == 0 or value == "0":
            return None
        try:
            val = int(value)
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None


class HoursRow(ApiModel):
    dayOfWeek: DayOfWeek
    opensAt: time
    closesAt: time


class HoursUpdate(ApiModel):
    hours: list[HoursRow] = Field(max_length=7)

    @model_validator(mode="after")
    def unique_days(self):
        if len({row.dayOfWeek for row in self.hours}) != len(self.hours):
            raise ValueError("Each weekday can appear once.")
        return self


class OverrideUpdate(ApiModel):
    isClosed: bool
    opensAt: time | None = None
    closesAt: time | None = None
    reason: str | None = Field(default=None, max_length=250)

    @field_validator("reason", mode="before")
    @classmethod
    def empty_reason_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value


class CustomerCreate(ApiModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def empty_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @model_validator(mode="after")
    def useful_record(self):
        if not self.name and not self.phone and not self.email:
            raise ValueError("Provide at least a name, phone number, or email address.")
        return self


class CustomerUpdate(ApiModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def empty_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value


class AppointmentCreate(ApiModel):
    customerId: UUID
    conversationId: UUID | None = None
    scheduledStart: datetime
    scheduledEnd: datetime | None = None
    status: AppointmentStatus = AppointmentStatus.PENDING
    customerName: str | None = Field(default=None, max_length=200)
    customerPhone: str | None = Field(default=None, max_length=100)
    customerEmail: EmailStr | None = None

    @field_validator("customerName", "customerPhone", mode="before")
    @classmethod
    def empty_contact_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("customerEmail", mode="before")
    @classmethod
    def empty_email_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value


class AppointmentUpdate(ApiModel):
    status: AppointmentStatus | None = None
    scheduledStart: datetime | None = None
    scheduledEnd: datetime | None = None
    customerName: str | None = Field(default=None, max_length=200)
    customerPhone: str | None = Field(default=None, max_length=100)
    customerEmail: EmailStr | None = None

    @field_validator("customerName", "customerPhone", mode="before")
    @classmethod
    def empty_contact_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value

    @field_validator("customerEmail", mode="before")
    @classmethod
    def empty_email_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        return value


class ConversationCreate(ApiModel):
    customerId: UUID | None = None
    externalConversationId: str | None = Field(default=None, min_length=1, max_length=500)
    currentIntent: str | None = Field(default=None, min_length=1, max_length=250)


class ConversationUpdate(ApiModel):
    customerId: UUID | None = None


class StatusUpdate(ApiModel):
    status: ConversationStatus


class StateUpdate(ApiModel):
    currentIntent: str | None = Field(default=None, min_length=1, max_length=250)
    currentStep: str | None = Field(default=None, min_length=1, max_length=250)
    collectedData: dict[str, Any]
    contextSummary: str | None = Field(default=None, max_length=20_000)
    lastAiResponse: str | None = Field(default=None, max_length=50_000)


class MessageCreate(ApiModel):
    content: str = Field(min_length=1, max_length=50_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
