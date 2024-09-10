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

from typing import Final, Optional

from wirepas_provisioning_server.helpers import convert_to_bytes, convert_to_int, ProvisioningDataException
from wirepas_provisioning_server.message import ProvisioningMethod
from wirepas_provisioning_server.migrate_config import ConfigFileMigration


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


class ProvisioningData(dict):
    # flake8: noqa: C901
    def __init__(self, config: Optional[str] = None):

        super(ProvisioningData, self).__init__()

        if config is not None:
            migration = ConfigFileMigration(config)
            migration.update()
            del migration

            try:
                with open(config, "r") as ymlfile:
                    cfg = yaml.safe_load(ymlfile)
            except yaml.YAMLError:
                raise ProvisioningDataException("Invalid data config file.")

            if cfg.get("version") != 1:
                raise ProvisioningDataException("Invalid data config file. Version must be 1")

            # Validate network parameters
            for name, network in cfg["networks"].items():
                try:
                    for parameter in [
                        "authentication_key",
                        "encryption_key",
                    ]:
                        network[parameter]
                except KeyError as e:
                    raise ProvisioningDataException(f"Invalid data config file. Network {name} must include {str(e)}.")

            for node_name, node_cfg in cfg["nodes"].items():
                if "network" not in node_cfg.keys():
                    raise ProvisioningDataException(f"Invalid data config file. Node {node_name} must include network.")
                network_name = node_cfg["network"]

                if "method" not in node_cfg.keys():
                    raise ProvisioningDataException(f"Invalid data config file. Node {node_name} must include method.")

                provision_methods = [e.value for e in ProvisioningMethod]
                if node_cfg["method"] not in provision_methods:
                    raise ProvisioningDataException(f"Node method must be one of {provision_methods}")

                if "uid" in node_cfg.keys():
                    uid: str | int | bytes = node_cfg["uid"]
                elif node_cfg["method"] == ProvisioningMethod.EXTENDED:
                    try:
                        uid = _generate_extended_uid(
                            node_cfg["authenticator_uid_type"],
                            node_cfg["authenticator_uid"],
                            node_cfg["node_uid_type"],
                            node_cfg["node_uid"],
                        )

                    except KeyError:
                        raise ProvisioningDataException(
                            f"Invalid data config file. Node {node_name} must include UID information."
                        )
                else:
                    raise ProvisioningDataException(f"Invalid data config file. Node {node_name} must include UID information")

                if "address" in cfg["networks"][network_name].keys():
                    network_address = convert_to_int(cfg["networks"][network_name]["address"])
                else:
                    network_address = None

                if "channel" in cfg["networks"][network_name].keys():
                    network_channel = convert_to_int(cfg["networks"][network_name]["channel"])
                else:
                    network_channel = None

                if "node_id" in node_cfg.keys():
                    node_id = convert_to_int(node_cfg["node_id"])
                else:
                    node_id = None

                if "node_role" in node_cfg.keys():
                    node_role = convert_to_bytes(node_cfg["node_role"])
                else:
                    node_role = None

                if "user_specific" in node_cfg.keys():
                    user_specific = dict()
                    for k in node_cfg["user_specific"]:
                        if k < 128 or k > 255:
                            raise KeyError
                        user_specific[k] = node_cfg["user_specific"][k]
                else:
                    user_specific = None

                if "factory_key" in node_cfg.keys():
                    factory_key = convert_to_bytes(node_cfg["factory_key"])
                else:
                    factory_key = None

                self.append(
                    convert_to_bytes(uid),
                    node_cfg["method"],
                    convert_to_bytes(cfg["networks"][network_name]["encryption_key"]),
                    convert_to_bytes(cfg["networks"][network_name]["authentication_key"]),
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
        node_id: Optional[int] = None,
        node_role: Optional[bytes] = None,
        user_specific: Optional[dict[int, bytes | str]] = None,
        factory_key: Optional[bytes] = None,
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
