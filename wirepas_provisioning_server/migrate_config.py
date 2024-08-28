#!/usr/bin/env python3
# Copyright 2024 Wirepas Ltd licensed under Apache License, Version 2.0
#
# See file LICENSE for full license details.
#
# Converts a config file from the old format to the new

from datetime import datetime
from typing import Final, Optional
from wirepas_provisioning_server.helpers import ProvisioningDataException, convert_to_bytes
from wirepas_provisioning_server.models import NetworkV1
import argparse
import logging
import uuid
import yaml

_LOGGER: Final = logging.getLogger(__name__)


class ConfigFileMigration:
    def __init__(self, filename: str):
        self.filename = filename

        _LOGGER.debug("Loading file: {}".format(self.filename))
        try:
            with open(filename, "r") as file:
                self._configuration: dict = yaml.safe_load(file)
        except yaml.YAMLError:
            raise ProvisioningDataException("Invalid data config file.")
        self.version: Optional[int] = self._configuration.get("version", None)

    def update(self) -> None:
        match self._configuration.get("version", None):
            case None:
                _LOGGER.info("Updating config file")
                # Old config file should not use any version key
                self._update_old_to_v1()
            case 1:
                _LOGGER.debug("Configuration file already to version 1")
            case _:
                raise ProvisioningDataException(f'Invalid data config file. Version {self._configuration["version"]}.')

    def _update_old_to_v1(self) -> None:
        """
        Converts the old format (no version) to V1, split networks and devices.
        """
        networks: list[NetworkV1] = []

        # Backup the old configuration file
        time_string = datetime.now().strftime("%y%m%d-%H%M%S.bak")
        with open(f"{self.filename}-{time_string}.backup", "x") as file:
            yaml.safe_dump(self._configuration, file, width=300, sort_keys=True)

        # Create a unique network list
        for node_configuration in self._configuration.values():
            existing_network: Optional[NetworkV1] = None
            address = node_configuration.get("network_address")
            channel = node_configuration.get("network_channel")
            authentication_key = convert_to_bytes(node_configuration["authentication_key"])
            encryption_key = convert_to_bytes(node_configuration["encryption_key"])

            for network in networks:
                # Detect if this network already exists
                if (
                    network.address == address
                    and network.channel == channel
                    and network.authentication_key == authentication_key
                    and network.encryption_key == encryption_key
                ):
                    existing_network = network
                    break

            if existing_network is None:
                existing_network = NetworkV1(
                    address=address,
                    channel=channel,
                    authentication_key=authentication_key,
                    encryption_key=encryption_key,
                    name=f"network_{uuid.uuid4()}",
                )
                networks.append(existing_network)

            # Update the node configuration
            node_configuration["network"] = existing_network.name
            for key in ["network_address", "network_channel"]:
                try:
                    del node_configuration[key]
                except KeyError:
                    # Pass as those keys are optional
                    pass
            del node_configuration["authentication_key"]
            del node_configuration["encryption_key"]

        configuration = {
            "version": 1,
            "nodes": self._configuration,
            "networks": {
                network.name: network.model_dump(exclude={"name"}, exclude_defaults=True, mode="json") for network in networks
            },
        }

        with open(self.filename, "w") as file:
            yaml.safe_dump(configuration, file, sort_keys=True, width=300)

        self.version = 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
    parser.add_argument(
        "--config",
        type=str,
        help='The path to your .yml config file: "examples/provisioning_config.yml"',
    )
    args = parser.parse_args()

    logging.basicConfig(format="%(levelname)s %(asctime)s %(message)s", level=logging.DEBUG)

    ConfigFileMigration(args.config).update()
