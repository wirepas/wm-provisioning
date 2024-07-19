"""
    Provisioning data
    =================

    .. Copyright:
        Copyright 2021 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""

import cbor2
import yaml
import logging

from typing import Optional

from wirepas_provisioning_server.message import ProvisioningMethod


def _generate_extended_uid(authenticator_uid_type_raw: str | int,
                           authenticator_uid_raw: str | int,
                           node_uid_type_raw: str | int,
                           node_uid_raw: str | int) -> bytes:
    """
    Generate extended UID bytes
    """

    authenticator_uid_type = _convert_to_bytes(authenticator_uid_type_raw)
    authenticator_uid = _convert_to_bytes(authenticator_uid_raw)
    node_uid_type = _convert_to_bytes(node_uid_type_raw)
    node_uid = _convert_to_bytes(node_uid_raw)

    def _any_is_not_bytes(*args: bytes | list[bytes]) -> bool:
        return any(not isinstance(arg, bytes) for arg in args)

    if _any_is_not_bytes(authenticator_uid_type, authenticator_uid, node_uid_type, node_uid):
        raise ValueError("Parameters must be convertible to bytes")

    if any(len(arg) != 1 for arg in [authenticator_uid_type, node_uid_type]):
        raise ValueError("UID type must be 1 byte")

    return b"".join([
        authenticator_uid_type,
        authenticator_uid,
        node_uid_type,
        node_uid
    ])


def _convert_to_bytes(param_raw: bytes | int | str ) -> bytes:
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


def _convert_to_int(param: int | str) -> int:
    if isinstance(param, str):
        param = int(param, 0)

    return param


class ProvisioningDataException(Exception):
    """
    Wirepas Provisioning data generic Exception
    """


class ProvisioningData(dict):
    def __init__(self, config: Optional[str]=None):

        super(ProvisioningData, self).__init__()

        if config is not None:
            try:
                with open(config, "r") as ymlfile:
                    cfg = yaml.safe_load(ymlfile)
            except yaml.YAMLError:
                raise ProvisioningDataException("Invalid data config file.")

            for node in cfg:

                if "method" not in cfg[node].keys():
                    raise ProvisioningDataException(f"Invalid data config file. {node} must include method.")

                provision_methods = [e.value for e in ProvisioningMethod]
                if cfg[node]["method"] not in provision_methods:
                    raise ProvisioningDataException(f"Method must be one of {provision_methods}")

                if "uid" in cfg[node].keys():
                    uid : str | int | bytes = cfg[node]["uid"]
                elif cfg[node]["method"] == ProvisioningMethod.EXTENDED:
                    try:
                        uid = _generate_extended_uid(
                            cfg[node]["authenticator_uid_type"],
                            cfg[node]["authenticator_uid"],
                            cfg[node]["node_uid_type"],
                            cfg[node]["node_uid"]
                        )

                    except KeyError:
                        raise ProvisioningDataException(f"Invalid data config file. {node} must include UID information.")
                else:
                    raise ProvisioningDataException(f"Invalid data config file. {node} must include UID information")

                if "network_address" in cfg[node].keys():
                    network_address = _convert_to_int(cfg[node]["network_address"])
                else:
                    network_address = None

                if "network_channel" in cfg[node].keys():
                    network_channel = _convert_to_int(cfg[node]["network_channel"])
                else:
                    network_channel = None

                if "node_id" in cfg[node].keys():
                    node_id = _convert_to_int(cfg[node]["node_id"])
                else:
                    node_id = None

                if "node_role" in cfg[node].keys():
                    node_role = _convert_to_bytes(cfg[node]["node_role"])
                else:
                    node_role = None

                if "user_specific" in cfg[node].keys():
                    user_specific = dict()
                    for k in cfg[node]["user_specific"]:
                        if k < 128 or k > 255:
                            raise KeyError
                        user_specific[k] = cfg[node]["user_specific"][k]
                else:
                    user_specific = None

                if "factory_key" in cfg[node].keys():
                    factory_key = _convert_to_bytes(cfg[node]["factory_key"])
                else:
                    factory_key = None

                if "encryption_key" not in cfg[node].keys():
                    raise ProvisioningDataException(f"Invalid data config file. {node} must include encryption_key.")
                if "authentication_key" not in cfg[node].keys():
                    raise ProvisioningDataException(f"Invalid data config file. {node} must include authentication_key.")


                self.append(
                    _convert_to_bytes(uid),
                    cfg[node]["method"],
                    _convert_to_bytes(cfg[node]["encryption_key"]),
                    _convert_to_bytes(cfg[node]["authentication_key"]),
                    network_address,
                    network_channel,
                    node_id=node_id,
                    node_role=node_role,
                    user_specific=user_specific,
                    factory_key=factory_key,
                )

    def append(
        self,
        uid: bytes,
        method: int,
        encryption_key: bytes,
        authentication_key: bytes,
        network_address: Optional[int],
        network_channel: Optional[int],
        node_id: Optional[int]=None,
        node_role: Optional[bytes]=None,
        user_specific: Optional[dict[int, bytes | str]]=None,
        factory_key: Optional[bytes]=None,
    ) -> None:

        # TODO : parameter checks
        self[uid] = dict(
            method=method,
            encryption_key=encryption_key,
            authentication_key=authentication_key,
        )
        if network_address is not None:
            self[uid]["network_address"] = network_address

        if network_channel is not None:
            self[uid]["network_channel"] = network_channel

        if node_id is not None:
            self[uid]["node_id"] = node_id

        if node_role is not None:
            self[uid]["node_role"] = node_role

        if user_specific is not None:
            self[uid]["user_specific"] = dict()
            for k in user_specific:
                # k should be an integer [128:255]
                # authorized type for value are string, byte string, integers
                self[uid]["user_specific"][k] = user_specific[k]

        if factory_key is not None:
            self[uid]["factory_key"] = factory_key

        logging.info("Append new UID: %s", uid.hex())
        logging.debug(" -  method: %s", method)
        logging.debug(" -  factory_key: %s", factory_key)
        logging.debug(" -  encryption_key: %s", encryption_key)
        logging.debug(" -  authentication_key: %s", authentication_key)
        logging.debug(" -  network_address: %s", network_address)
        logging.debug(" -  network_channel: %s", network_channel)
        logging.debug(" -  node_id: %s", node_id)
        logging.debug(" -  node_role: %s", node_role)
        if "user_specific" in self[uid].keys():
            for k in self[uid]["user_specific"]:
                logging.debug(" - %d : %s", k, self[uid]["user_specific"][k])

    def getCbor(self, uid: bytes) -> bytes:
        self_dic = dict()

        self_dic[0] = self[uid]["encryption_key"]
        self_dic[1] = self[uid]["authentication_key"]

        if "network_address" in self[uid].keys():
            self_dic[2] = self[uid]["network_address"]

        if "network_channel" in self[uid].keys():
            self_dic[3] = self[uid]["network_channel"]

        if "node_id" in self[uid].keys():
            self_dic[4] = self[uid]["node_id"]

        if "node_role" in self[uid].keys():
            self_dic[5] = self[uid]["node_role"]

        if "user_specific" in self[uid].keys():
            for key in self[uid]["user_specific"]:
                self_dic[key] = self[uid]["user_specific"][key]

        return cbor2.dumps(self_dic)
