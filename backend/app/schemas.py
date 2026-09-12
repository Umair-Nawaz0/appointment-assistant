from __future__ import annotations

import re
from datetime import datetime, time
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Channel(StrEnum):
    WHATSAPP = "WHATSAPP"
    PHONE = "PHONE"
    SMS = "SMS"
    EMAIL = "EMAIL"
    INSTAGRAM = "INSTAGRAM"
    WEBSITE = "WEBSITE"


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
    industry: str | None = Field(default=None, min_length=1, max_length=120)


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
    address: str | None = Field(default=None, min_length=1, max_length=250)
    city: str | None = Field(default=None, min_length=1, max_length=250)
    stateProvince: str | None = Field(default=None, min_length=1, max_length=250)
    postalCode: str | None = Field(default=None, min_length=1, max_length=250)
    countryCode: str | None = Field(default=None, min_length=2, max_length=2)
    industry: str | None = Field(default=None, min_length=1, max_length=250)
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator("countryCode")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SettingsUpdate(ApiModel):
    appointmentDurationMinutes: int = Field(ge=1, le=1440)
    bookingWindowDays: int = Field(ge=1, le=3650)
    maximumAppointmentsPerDay: int | None = Field(default=None, gt=0)
    allowCancellation: bool
    allowReschedule: bool
    collectPhone: bool
    collectEmail: bool
    confirmationRequired: bool


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
    reason: str | None = Field(default=None, min_length=1, max_length=250)


class ChannelUpdate(ApiModel):
    enabled: bool
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    externalAccountId: str | None = Field(default=None, min_length=1, max_length=250)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityInput(ApiModel):
    channel: Channel
    identifier: str = Field(min_length=1, max_length=500)
    displayName: str | None = Field(default=None, min_length=1, max_length=200)
    verified: bool = False
    isPrimary: bool = False


class CustomerCreate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    identities: list[IdentityInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def useful_record(self):
        if self.name is None and not self.identities:
            raise ValueError("Provide a name or at least one channel identity.")
        return self


class CustomerUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class AppointmentCreate(ApiModel):
    customerId: UUID
    conversationId: UUID | None = None
    scheduledStart: datetime
    scheduledEnd: datetime | None = None
    status: AppointmentStatus = AppointmentStatus.PENDING
    createdChannel: Channel
    customerName: str | None = Field(default=None, min_length=1, max_length=200)
    customerPhone: str | None = Field(default=None, min_length=1, max_length=100)
    customerEmail: EmailStr | None = None


class AppointmentUpdate(ApiModel):
    status: AppointmentStatus | None = None
    scheduledStart: datetime | None = None
    scheduledEnd: datetime | None = None
    customerName: str | None = Field(default=None, min_length=1, max_length=200)
    customerPhone: str | None = Field(default=None, min_length=1, max_length=100)
    customerEmail: EmailStr | None = None


class ConversationCreate(ApiModel):
    customerId: UUID
    channel: Channel
    externalConversationId: str | None = Field(default=None, min_length=1, max_length=500)
    currentIntent: str | None = Field(default=None, min_length=1, max_length=250)


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
