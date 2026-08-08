from pydantic import BaseModel
from typing import Any


class ListingCreate(BaseModel):
    title: str | None = None
    property_type: str | None = None
    deal_type: str | None = None
    city: str | None = None
    district: str | None = None
    neighborhood: str | None = None
    address: str | None = None
    rooms: str | None = None
    floor: str | None = None
    area_sqm: int | None = None
    price: int | None = None
    parking: int = 0
    pool: bool = False
    shelter: str | None = None
    elevator: bool = False
    infrastructure: list[str] = []
    description: str | None = None
    photos: list[str] = []
    active: bool = True
    user_id: int | None = None
    seller_type: str | None = None
    source: str = "manual"
    contact: str | None = None
    email: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = None
    property_type: str | None = None
    deal_type: str | None = None
    city: str | None = None
    district: str | None = None
    neighborhood: str | None = None
    address: str | None = None
    rooms: str | None = None
    floor: str | None = None
    area_sqm: int | None = None
    price: int | None = None
    parking: int | None = None
    pool: bool | None = None
    shelter: str | None = None
    elevator: bool | None = None
    infrastructure: list[str] | None = None
    description: str | None = None
    photos: list[str] | None = None
    active: bool | None = None
    contact: str | None = None
    email: str | None = None
    views: int | None = None
    view_requests: int | None = None


class SubscriptionCreate(BaseModel):
    filters: dict[str, Any]


class SubscriptionUpdate(BaseModel):
    last_result_ids: list[int] | None = None
    active: bool | None = None
    last_checked: str | None = None


class PaidSubscriptionActivate(BaseModel):
    plan_type: str
    days: int


class CRMContactCreate(BaseModel):
    contact_type: str
    name: str | None = None
    phone: str | None = None
    telegram: str | None = None
    region: str | None = None
    city: str | None = None
    notes: str | None = None


class CRMContactUpdate(BaseModel):
    contact_type: str | None = None
    name: str | None = None
    phone: str | None = None
    telegram: str | None = None
    region: str | None = None
    city: str | None = None
    notes: str | None = None
    active: bool | None = None


class CRMDealCreate(BaseModel):
    contact_id: int
    description: str | None = None
    amount: int | None = None
    status: str = "new"


class CRMDealUpdate(BaseModel):
    description: str | None = None
    amount: int | None = None
    status: str | None = None


class CRMNoteCreate(BaseModel):
    contact_id: int
    text: str


class AgentProfileUpsert(BaseModel):
    owner_name: str | None = None
    owner_phone: str | None = None
    email: str | None = None
    lang: str | None = None


class ServiceProviderCreate(BaseModel):
    service_type: str
    region: str | None = None
    city: str | None = None
    description: str | None = None
    price_description: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    user_id: int | None = None


class ServiceProviderUpdate(BaseModel):
    service_type: str | None = None
    region: str | None = None
    city: str | None = None
    description: str | None = None
    price_description: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    active: bool | None = None


class ReferralCreate(BaseModel):
    referrer_id: int
    new_user_id: int


class ReviewCreate(BaseModel):
    listing_id: int
    user_id: int
    rating: int
    comment: str | None = None


class AnalyticsEvent(BaseModel):
    user_id: int | None = None
    event_type: str
    payload: dict[str, Any] = {}


class ViewRequesterCreate(BaseModel):
    listing_id: int
    user_id: int
    username: str | None = None
    name: str | None = None


class BackofficeSession(BaseModel):
    token: str
    expires_at: str


class FavoriteCreate(BaseModel):
    saved_price: int | None = None
