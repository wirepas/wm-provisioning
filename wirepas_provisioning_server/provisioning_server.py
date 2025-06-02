#!/usr/bin/env python3
# Copyright 2021 Wirepas Ltd licensed under Apache License, Version 2.0
#
# See file LICENSE for full license details.

import time
import os
import argparse
import logging

from typing import Optional

from wirepas_mqtt_library import WirepasNetworkInterface
from wirepas_mesh_messaging import GatewayResultCode
from wirepas_mesh_messaging.received_data import ReceivedDataEvent

from wirepas_provisioning_server.session import ProvisioningSession, ProvisioningStatus
from wirepas_provisioning_server.message import (
    ProvisioningMessageFactory,
    ProvisioningMessageException,
)
from wirepas_provisioning_server.data import ProvisioningData
from wirepas_provisioning_server.events import ProvisioningEventPacketReceived


def get_default_value_from_env(env_var_name: str, default: Optional[bool | int | str] = None) -> Optional[bool | int | str]:
    value = os.environ.get(env_var_name, default)
    if value is not None and value == "":
        return None
    else:
        return value


class ProvisioningServer:
    def __init__(
        self,
        interface: WirepasNetworkInterface,
        settings: str,
    ):
        self.interface = interface
        self.sessions: dict[tuple[Optional[int], bytes, int], ProvisioningSession] = {}
        self.data = ProvisioningData(settings)

        # Register for data packets to provisioning endpoints
        for ep in self.data.provisioning_data_conf.data_endpoints:
            interface.register_uplink_traffic_cb(self.on_data_received, src_ep=ep.req_ep[0], dst_ep=ep.req_ep[1])

    def on_session_finish(self, key: tuple[int, bytes, int], status: ProvisioningStatus) -> None:
        logging.info(
            "Provisioning Session %s terminated with result: %s.",
            self.sessions[key],
            status,
        )
        del self.sessions[key]

    def on_data_received(self, data: ReceivedDataEvent) -> None:
        try:
            msg_data = ProvisioningMessageFactory.map(data)
            req_ep = (data.source_endpoint, data.destination_endpoint)
        except ProvisioningMessageException as e:
            print(e)
            return
        ev = ProvisioningEventPacketReceived(msg_data)
        logging.debug("Got new packet: %s.", msg_data)

        try:
            self.sessions[msg_data.msg_id].event_q.put(ev)
            logging.debug("Found SM with id: %s.", msg_data)
        except KeyError:
            resp_ep = self.data.provisioning_data_conf.get_resp_ep_by_req_ep(req_ep)

            logging.info("Create new SM with id: %s, ep:%d,%d.", msg_data, resp_ep[0], resp_ep[1])
            self.sessions[msg_data.msg_id] = ProvisioningSession(
                self.interface.send_message,
                resp_ep,
                msg_data.msg_id,
                self.data,
                self.on_session_finish,
            )
            self.sessions[msg_data.msg_id].event_q.put(ev)

    def loop(self, sleep_for: float = 2) -> None:
        """
        Server loop

        """
        try:
            while True:
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            pass

        logging.info("Stopping Provisioning Server.")

    def send_packet(
        self,
        gw_id: str,
        sink_id: str,
        dest: int,
        src_ep: int,
        dst_ep: int,
        qos: int,
        payload: bytes,
    ) -> Optional[GatewayResultCode]:
        logging.debug("Sending packet (%s).", payload)
        try:
            return self.interface.send_message(gw_id, sink_id, dest, src_ep, dst_ep, payload, qos)
        except TimeoutError:
            logging.warning("Sending packet failed with timeout exception.")
            return GatewayResultCode.GW_RES_INTERNAL_ERROR


def main() -> None:
    """
    Main service for provisioning server
    """

    parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
    parser.add_argument(
        "--host",
        default=get_default_value_from_env("WM_SERVICES_MQTT_HOSTNAME"),
        help="MQTT broker address",
    )
    parser.add_argument(
        "--port",
        default=get_default_value_from_env("WM_SERVICES_MQTT_PORT", 8883),
        type=int,
        help="MQTT broker port",
    )
    parser.add_argument(
        "--insecure",
        default=get_default_value_from_env("WM_SERVICES_MQTT_INSECURE", False),
        type=lambda x: x.lower() == "true",
        choices=[True, False],
        help="MQTT security option",
    )
    parser.add_argument(
        "--username",
        default=get_default_value_from_env("WM_SERVICES_MQTT_USERNAME", "mqttmasteruser"),
        help="MQTT broker username",
    )
    parser.add_argument(
        "--password",
        default=get_default_value_from_env("WM_SERVICES_MQTT_PASSWORD"),
        help="MQTT broker password",
    )
    parser.add_argument(
        "--config",
        default=get_default_value_from_env("WM_PROV_CONFIG", "/home/wirepas/wm-provisioning/vars/settings.yml"),
        type=str,
        help='The path to your .yml config file: "examples/provisioning_config.yml"',
    )
    parser.add_argument(
        "--loglevel",
        default=get_default_value_from_env("WM_PROV_LOG_LEVEL", "INFO"),
        type=str,
        help=f'Log level, choose one of {", ".join(logging._nameToLevel.keys())} ',
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s %(asctime)s %(message)s",
        level=logging._nameToLevel[args.loglevel] or logging.INFO,
    )

    wni = WirepasNetworkInterface(args.host, args.port, args.username, args.password, args.insecure)

    srv = ProvisioningServer(interface=wni, settings=args.config)
    srv.loop()


if __name__ == "__main__":
    main()
