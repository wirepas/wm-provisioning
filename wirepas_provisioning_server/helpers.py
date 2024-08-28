"""
    Provisioning helpers
    ===================

    .. Copyright:
        Copyright 2024 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""


class ProvisioningDataException(Exception):
    """
    Wirepas Provisioning data generic Exception
    """


def convert_to_bytes(param_raw: bytes | int | str) -> bytes:
    if isinstance(param_raw, str):
        if param_raw.upper().startswith("0X"):
            param_raw = param_raw.upper().replace("0X", "")
            param = bytes.fromhex(param_raw)
        else:
            param = bytes(param_raw, "utf-8")
    elif isinstance(param_raw, int):
        param = param_raw.to_bytes(max(1, (param_raw.bit_length() + 7)) // 8, byteorder="big")
    else:
        param = param_raw

    return param


def convert_to_int(param: int | str) -> int:
    if isinstance(param, str):
        param = int(param, 0)

    return param
