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


def _convert_to_bytes(param):
    if isinstance(param, str):
        if param.upper().startswith("0X"):
            param = param.upper().replace("0X", "")
            param = bytes.fromhex(param)
        else:
            param = bytes(param, "utf-8")
    elif isinstance(param, int):
        param.to_bytes((param.bit_length() + 7) // 8, byteorder="big")

    return param


def _convert_to_int(param):
    if isinstance(param, str):
        param = int(param, 0)

    return param


class ProvisioningDataException(Exception):
    """
    Wirepas Provisioning data generic Exception
    """


class ProvisioningData(dict):
    def __init__(self, config=None):

        super(ProvisioningData, self).__init__()

        if config is not None:
            try:
                with open(config, "r") as ymlfile:
                    cfg = yaml.safe_load(ymlfile)
            except yaml.YAMLError:
                raise ProvisioningDataException("Invalid data config file.")

            for uid in cfg:
                if "network_address" in cfg[uid].keys():
                    network_address = _convert_to_int(cfg[uid]["network_address"])
                else:
                    network_address = None

                if "network_channel" in cfg[uid].keys():
                    network_channel = _convert_to_int(cfg[uid]["network_channel"])
                else:
                    network_channel = None

                if "node_id" in cfg[uid].keys():
                    node_id = _convert_to_int(cfg[uid]["node_id"])
                else:
                    node_id = None

                if "node_role" in cfg[uid].keys():
                    node_role = _convert_to_bytes(cfg[uid]["node_role"])
                else:
                    node_role = None

                if "user_specific" in cfg[uid].keys():
                    user_specific = dict()
                    for k in cfg[uid]["user_specific"]:
                        if k < 128 or k > 255:
                            raise KeyError
                        user_specific[k] = cfg[uid]["user_specific"][k]
                else:
                    user_specific = None

                if "factory_key" in cfg[uid].keys():
                    factory_key = _convert_to_bytes(cfg[uid]["factory_key"])
                else:
                    factory_key = None

                self.append(
                    _convert_to_bytes(uid),
                    cfg[uid]["method"],
                    _convert_to_bytes(cfg[uid]["encryption_key"]),
                    _convert_to_bytes(cfg[uid]["authentication_key"]),
                    network_address,
                    network_channel,
                    node_id=node_id,
                    node_role=node_role,
                    user_specific=user_specific,
                    factory_key=factory_key,
                )

    def append(
        self,
        uid,
        method,
        encryption_key,
        authentication_key,
        network_address,
        network_channel,
        node_id=None,
        node_role=None,
        user_specific=None,
        factory_key=None,
    ):

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

        logging.info("Append new UID: %s", uid)
        logging.debug(" -  method: %s", self[uid]["method"])
        if "factory_key" in self[uid].keys():
            logging.debug(" -  factory_key: %s", self[uid]["factory_key"])
        logging.debug(" -  encryption_key: %s", self[uid]["encryption_key"])
        logging.debug(" -  authentication_key: %s", self[uid]["authentication_key"])
        logging.debug(" -  network_address: %s", self[uid]["network_address"])
        logging.debug(" -  network_channel: %s", self[uid]["network_channel"])
        if "node_id" in self[uid].keys():
            logging.debug(" -  node_id: %s", self[uid]["node_id"])
        if "node_role" in self[uid].keys():
            logging.debug(" -  node_role: %s", self[uid]["node_role"])
        if "user_specific" in self[uid].keys():
            for k in self[uid]["user_specific"]:
                logging.debug(" - %d : %s", k, self[uid]["user_specific"][k])

    def getCbor(self, uid):
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
