"""
    Provisioning data models
    ===================

    .. Copyright:
        Copyright 2024 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from wirepas_provisioning_server.helpers import convert_to_bytes


class NetworkV1(BaseModel):
    """Holding network parameters for the V1 configuration file format."""

    address: Optional[int] = None
    channel: Optional[int] = None
    authentication_key: bytes
    encryption_key: bytes
    name: str = Field(frozen=True)

    @field_validator("authentication_key", "encryption_key", mode="before")
    @classmethod
    def check_key(cls, key: bytes | int | str) -> bytes:
        return convert_to_bytes(key)

    class Config:
        json_encoders = {bytes: lambda value: f"0x{value.hex()}"}
