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

from wirepas_provisioning_server.helpers import convert_to_bytes, convert_to_int, ProvisioningDataException
from wirepas_provisioning_server.message import ProvisioningMethod
from wirepas_provisioning_server.models import NetworkV1, NodeV1
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

            networks: dict[str, NetworkV1] = {}
            for name, network in cfg["networks"].items():
                networks[name] = NetworkV1(
                    **network,
                    name=name,
                )

            for name, raw_node in cfg["nodes"].items():
                raw_node["network"] = networks[raw_node["network"]]
                node = NodeV1(
                    **raw_node,
                    name=name,
                )
                self[node.uid] = node

                logging.info("Append new UID: 0x%s", node.uid.hex().upper())
                logging.debug(" -  method: %s", node.method)
                if node.factory_key is not None:
                    logging.debug(" -  factory_key: 0x%s", node.factory_key.hex().upper())
                else:
                    logging.debug(" -  factory_key: None")
                logging.debug(" -  encryption_key: 0x%s", node.network.encryption_key.hex().upper())
                logging.debug(" -  authentication_key: 0x%s", node.network.authentication_key.hex().upper())
                logging.debug(" -  network_address: %s", node.network.address)
                logging.debug(" -  network_channel: %s", node.network.channel)
                logging.debug(" -  node_id: %s", node.node_id)
                logging.debug(" -  node_role: %s", node.role)
                if node.user_specific is not None:
                    logging.debug(" -  User specific data:: %s", node.role)
                    for index, value in node.user_specific.items():
                        logging.debug(" -    %d: %s", index, value)
