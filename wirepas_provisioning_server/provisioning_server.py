#!/usr/bin/env python3
# Copyright 2021 Wirepas Ltd licensed under Apache License, Version 2.0
#
# See file LICENSE for full license details.

import time
import os
import argparse
import logging
import threading

from wirepas_mqtt_library import WirepasNetworkInterface
from wirepas_mesh_messaging import GatewayResultCode

from wirepas_provisioning_server.session import ProvisioningSession, ProvisioningStatus
from wirepas_provisioning_server.message import ProvisioningMessageFactory, ProvisioningMessageException
from wirepas_provisioning_server.data import ProvisioningData
from wirepas_provisioning_server.events import ProvisioningEventPacketReceived


def get_default_value_from_env(env_var_name, default=None):
    value = os.environ.get(env_var_name, default)
    if value is not None and value == "":
        return None
    else:
        return value


class ProvisioningServer():
    def __init__(
        self,
        interface,
        settings,
    ):
        self.interface = interface
        self.sessions = {}
        self.data = ProvisioningData(settings)

        # Register for packets on Provisioning Endpoints [246:255]
        interface.register_data_cb(self.on_data_received, src_ep=246, dst_ep=255)


    def on_session_finish(self, key, status):
        logging.info("Provisioning Session %s terminated with result: %s.", self.sessions[key], status)
        del self.sessions[key]
        return

    def on_data_received(self, data):
        try:
            msg_data = ProvisioningMessageFactory.map(data)
        except ProvisioningMessageException as e:
            print(e)
            return
        ev = ProvisioningEventPacketReceived(msg_data)
        logging.debug("Got new packet: %s.", msg_data)

        try:
            self.sessions[msg_data.msg_id].event_q.put(ev)
            logging.debug("Found SM with id: %s.", msg_data)
        except KeyError:
            logging.info("Create new SM with id: %s.", msg_data)
            self.sessions[msg_data.msg_id] = ProvisioningSession(
                self.interface.send_message,
                msg_data.msg_id,
                self.data,
                self.on_session_finish
            )
            self.sessions[msg_data.msg_id].event_q.put(ev)

    def loop(self, sleep_for=2):
        """
        Server loop

        """
        try:
            while True:
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            pass

        logging.info("Stopping Provisioning Server.")

    def send_packet(self, gw_id, sink_id, dest, src_ep, dst_ep, qos, payload):
        logging.debug("Sending packet (%s).", payload)
        try:
            return self.interface.send_message(gw_id, sink_id, dest, src_ep, dst_ep, qos, payload)
        except TimeoutError:
            logging.warning("Sending packet failed with timeout exception.")
            return GatewayResultCode.GW_RES_INTERNAL_ERROR


def main():
    """
        Main service for provisioning server
    """

    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument('--host', default=get_default_value_from_env('WM_SERVICES_MQTT_HOSTNAME'), help="MQTT broker address")
    parser.add_argument('--port',
                        default=get_default_value_from_env('WM_SERVICES_MQTT_PORT', 8883),
                        type=int,
                        help='MQTT broker port')
    parser.add_argument('--username',
                        default=get_default_value_from_env('WM_SERVICES_MQTT_USERNAME', 'mqttmasteruser'),
                        help='MQTT broker username')
    parser.add_argument('--password',
                        default=get_default_value_from_env('WM_SERVICES_MQTT_PASSWORD'),
                        help='MQTT broker password')
    parser.add_argument('--config',
                        default=get_default_value_from_env('WM_PROV_CONFIG',
                                                           '/home/wirepas/wm-provisioning/vars/settings.yml'),
                        type=str,
                        help='The path to your .yml config file: \"examples/provisioning_config.yml\"')
    args = parser.parse_args()

    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s', level=logging.INFO)

    wni = WirepasNetworkInterface(args.host, args.port, args.username, args.password)

    srv = ProvisioningServer(interface=wni, settings=args.config)
    srv.loop()


if __name__ == "__main__":
    main()
