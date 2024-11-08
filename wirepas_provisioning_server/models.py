"""
    Provisioning data models
    ===================

    .. Copyright:
        Copyright 2024 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""

import cbor2
from enum import IntEnum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Final, Optional
from wirepas_provisioning_server.message import ProvisioningMethod
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
        key = convert_to_bytes(key)
        if len(key) != 16:
            raise ValueError(f'Keys must be 16 bytes, got "{len(key)}"')
        return key

    class Config:
        json_encoders = {bytes: lambda value: f"0x{value.hex()}"}


class NodeV1(BaseModel):
    """Holding device parameters for the V1 configuration file format."""

    class AuthenticatorUIDType(IntEnum):
        """Node UID types."""

        UUID4 = 1

    class NodeUIDType(IntEnum):
        """Node UID types."""

        UUID4 = 1

    class UserSpecificType(BaseModel):
        """Holding user specific parameters."""

        key: int = Field(ge=128, le=255)
        value: Any

    node_id: Optional[int] = Field(default=None, description="Address to be allocated to the node.")
    factory_key: Optional[bytes] = Field(default=None, description="Key to secure the provisioning process.")
    method: ProvisioningMethod = Field(description="Provisioning method - unsecured: 0, secured: 1, extended: 3.")
    name: str = Field(description="Node label")
    network: NetworkV1 = Field(description="Network parameters where the node will be provisioned.")
    role: Optional[bytes] = Field(
        default=None,
        description="Role of the node - https://github.com/wirepas/wm-sdk-2_4/blob/rel_1.5.2_2_4/libraries/dualmcu/api/DualMcuAPI.md#cNodeRole",  # noqa: E501
    )
    uid: bytes = Field(default=None, description="Unique identifier of the node.")
    user_specific: Optional[dict[int, Any]] = Field(
        default=None, description="Dict containing user specific parameters to be sent to the device."
    )

    authenticator_uid_type: Optional[AuthenticatorUIDType] = None
    authenticator_uid: Optional[bytes] = None  # TODO add a validation
    node_uid_type: Optional[NodeUIDType] = None
    node_uid: Optional[bytes] = None  # TODO add a validation

    @staticmethod
    def _generate_extended_uid(
        authenticator_uid_type_raw: str | int,
        authenticator_uid_raw: str | int,
        node_uid_type_raw: str | int,
        node_uid_raw: str | int,
    ) -> bytes:
        """
        Generate extended UID bytes
        """

        authenticator_uid_type = convert_to_bytes(authenticator_uid_type_raw)
        authenticator_uid = convert_to_bytes(authenticator_uid_raw)
        node_uid_type = convert_to_bytes(node_uid_type_raw)
        node_uid = convert_to_bytes(node_uid_raw)

        def _any_is_not_bytes(*args: bytes | list[bytes]) -> bool:
            return any(not isinstance(arg, bytes) for arg in args)

        if _any_is_not_bytes(authenticator_uid_type, authenticator_uid, node_uid_type, node_uid):
            raise ValueError("Parameters must be convertible to bytes")

        if any(len(arg) != 1 for arg in [authenticator_uid_type, node_uid_type]):
            raise ValueError("UID type must be 1 byte")

        return b"".join([authenticator_uid_type, authenticator_uid, node_uid_type, node_uid])

    @field_validator("factory_key", mode="before")
    @classmethod
    def check_factory_key(cls, key: bytes | int | str) -> bytes:
        key = convert_to_bytes(key)
        if len(key) != 32:
            raise ValueError(f'Factory key must be 32 bytes, got "{len(key)}"')
        return key

    @field_validator("node_id", mode="before")
    @classmethod
    def check_node_id(cls, node_id: int) -> int:
        if None or (node_id >= 0x00000001 and node_id <= 0x7FFFFFFF) or (node_id >= 0x81000000 and node_id <= 0xFFFFFFFD):
            return node_id
        else:
            raise ValueError(
                f'Node ID must be None, between [0x1; 0x7FFFFFFF] or [0x81000000, 0xFFFFFFFD], got "{node_id} (0x{node_id:08x})"'  # noqa: E501
            )

    @field_validator("uid", mode="before")
    @classmethod
    def check_uid(cls, uid: bytes | str) -> bytes:
        uid = convert_to_bytes(uid)
        if len(uid) < 1 or len(uid) > 79:
            raise ValueError(f'UID must be between 1 and 79 bytes, got "{len(uid)}".')
        return uid

    @field_validator("authenticator_uid", "node_uid", mode="before")
    @classmethod
    def check_extended_uids(cls, uid: bytes | str) -> bytes:
        uid = convert_to_bytes(uid)
        if len(uid) != 16:
            raise ValueError(f'authenticator_uid and node_uid must be 16 bytes, got "{len(uid)}".')
        return uid

    @field_validator("role", mode="before")
    @classmethod
    def check_role(cls, role_raw: bytes | int | str) -> bytes:
        ALLOWED_ROLES: Final = [0x1, 0x2, 0x3, 0x11, 0x12, 0x13, 0x82, 0x83, 0x92, 0x93]

        if isinstance(role_raw, str):
            role_bytes = convert_to_bytes(role_raw)
        elif isinstance(role_raw, int):
            role_bytes = bytes([role_raw])
        else:
            role_bytes = role_raw

        if len(role_bytes) != 1:
            raise ValueError(f'Role must be 1 byte, got "{len(role_bytes)}".')

        if role_bytes[0] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role value: 0x{role_bytes.hex()}.")
        return role_bytes

    @field_validator("user_specific", mode="before")
    @classmethod
    def check_user_specific_index(cls, data: dict[int, Any]) -> dict[int, Any]:
        for index in data.keys():
            if index < 128 or index > 255:
                raise ValueError(f'user_specific index must be between 128 and 255, got "{index}"')
        return data

    @model_validator(mode="after")
    def compute_uid(self: "NodeV1") -> "NodeV1":
        """Compute uid from extended uid parameters, if not provided."""
        if self.method == ProvisioningMethod.EXTENDED and self.uid is None:
            for attribute in ["authenticator_uid_type", "authenticator_uid", "node_uid_type", "node_uid"]:
                if getattr(self, attribute) is None:
                    raise ValueError(
                        f"Invalid extended uid parameters: {attribute} should be provided if method is ProvisioningMethod.EXTENDED (3)"  # noqa: E501
                    )
            self.uid = self._generate_extended_uid(
                self.authenticator_uid_type,
                self.authenticator_uid,
                self.node_uid_type,
                self.node_uid,
            )

        elif self.uid is None:
            raise ValueError("Invalid uid parameters: uid should be provided if method is not ProvisioningMethod.EXTENDED (3)")
        return self

    def getCbor(self) -> bytes:
        """Returns the CBOR representation of the node."""
        data = {}

        data[0] = self.network.encryption_key
        data[1] = self.network.authentication_key

        if self.network.address is not None:
            data[2] = self.network.address  # type: ignore[assignment]
        if self.network.channel is not None:
            data[3] = self.network.channel  # type: ignore[assignment]
        if self.node_id is not None:
            data[4] = self.node_id  # type: ignore[assignment]
        if self.role is not None:
            data[5] = self.role
        if self.user_specific is not None:
            for index, value in self.user_specific.items():
                # Data conversion is handled by cbor2
                data[index] = value

        return cbor2.dumps(data)
