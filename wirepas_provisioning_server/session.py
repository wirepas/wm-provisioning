"""
    Provisioning session (state machine)
    ==========================

    .. Copyright:
        Copyright 2021 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""

import queue
import logging
import threading
import enum
import random

from Crypto.Hash import CMAC
from Crypto.Cipher import AES
from Crypto.Util import Counter

from typing import Callable, Optional

from wirepas_mesh_messaging import GatewayResultCode

from .data import ProvisioningData
from .events import ProvisioningEventPacketReceived, ProvisioningEvent, ProvisioningEventTimeout
from .message import (
    ProvisioningMessage,
    ProvisioningMessageSTART,
    ProvisioningMessageDATA,
    ProvisioningMessageNACK,
    ProvisioningMessageTypes,
    ProvisioningNackReason,
    ProvisioningMethod,
)


class ProvisioningStates(enum.Enum):
    """Provisioning states"""

    IDLE = 0
    WAIT_RESPONSE = 2


class ProvisioningStatus(enum.Enum):
    """Provisioning status"""

    ONGOING = 0
    SUCCESS = 1
    FAILURE = 2
    ERROR_NO_ACK = 3
    ERROR_SENDING_DATA = 4
    ERROR_SENDING_NACK = 5
    ERROR_NOT_AUTHORIZED = 6
    ERROR_NOT_START = 7
    ERROR_INVALID_STATE = 8
    ERROR_NACK_RECEIVED = 9
    ERROR_NO_RESPONSE = 10


class ProvisioningSession(threading.Thread):
    def __init__(
        self,
        send_func: Callable,
        resp_ep: tuple[int, int],
        session_id: tuple[Optional[int], bytes, int],
        data: ProvisioningData,
        on_session_finish: Callable,
        retry: int = 1,
        timeout: int = 180,
    ):
        super(ProvisioningSession, self).__init__()

        self.send_func = send_func
        self.resp_ep = resp_ep
        self.session_id = session_id
        self.data = data
        self.retry = retry
        self.timeout = timeout
        self.finish_cb = on_session_finish

        self.event_q: queue.Queue[ProvisioningEvent] = queue.Queue()

        self.counter = random.getrandbits(16)

        self.state = ProvisioningStates.IDLE
        self.status = ProvisioningStatus.ONGOING
        self._timer: Optional[threading.Timer] = None

        self.sink_id: Optional[int] = None
        self.gw_id: Optional[int] = None
        self._tx_time: int = 0

        self.daemon = True
        self.start()

    def __str__(self) -> str:
        return "".join(
            [
                "[{:08X}".format(self.session_id[0]) if self.session_id[0] is not None else "[None",
                ", ",
                "".join("{:02X}".format(x) for x in self.session_id[1]),
                ", {:02X}".format(self.session_id[2]),
                "]",
            ]
        )

    def _timeout(self) -> None:
        self.event_q.put(ProvisioningEventTimeout())

    def _update_origin(self, msg: ProvisioningMessage) -> None:
        if msg.tx_time and self._tx_time < msg.tx_time:
            self.sink_id = msg.sink_id
            self.gw_id = msg.gw_id
            self._tx_time = msg.tx_time

    def _timer_start(self, timeout: float) -> None:
        if self._timer is not None:
            self._timer_cancel()
        self._timer = threading.Timer(self.timeout, self._timeout)
        self._timer.start()

    def _timer_cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer.join()
            self._timer = None

    def _send_packet(self, payload: bytes) -> GatewayResultCode:
        logging.debug("  - Sending packet (%s).", payload)
        try:
            return self.send_func(
                gw_id=self.gw_id,
                sink_id=self.sink_id,
                dest=self.session_id[0],
                src_ep=self.resp_ep[0],
                dst_ep=self.resp_ep[1],
                qos=1,
                payload=payload,
            )
        except TimeoutError:
            logging.warning("  - Sending packet failed with timeout exception.")
            return GatewayResultCode.GW_RES_INTERNAL_ERROR

    def _encrypt_packet(self, uid: bytes, iv: bytes, plain_text: bytes) -> bytes:
        enc_key = self.data[uid]["factory_key"][16:32]
        auth_key = self.data[uid]["factory_key"][0:16]

        logging.info("  - Encrypt DATA packet")
        # Increment counter
        self.counter += 1
        logging.debug("   -  IV: %s", "".join("{:02X}".format(x) + " " for x in iv))
        logging.debug("   - Counter : %s", str(self.counter))

        # Authenticate Header + Payload
        to_auth = ProvisioningMessageDATA(self.session_id[1], self.session_id[2], self.counter, plain_text).payload

        # Create a CMAC / OMAC1 object.
        cobj = CMAC.new(auth_key, ciphermod=AES)
        cobj.update(to_auth)

        # MIC is 5 first bytes
        mic = cobj.digest()[0:5]

        # Encrypt payload + mic
        # Generate Initial Counter Block (ICB).
        ctr_bytes = self.counter + int.from_bytes(iv, byteorder="little", signed=False)
        ctr_bytes = ctr_bytes % (2**128)
        icb = ctr_bytes.to_bytes(16, byteorder="little")

        logging.debug("   -  ICB: %s", "".join("{:02X}".format(x) + " " for x in icb))

        # Create an AES Counter (CTR) mode cipher using ICB.
        ctr = Counter.new(
            128,
            little_endian=True,
            allow_wraparound=True,
            initial_value=int.from_bytes(icb, byteorder="little", signed=False),
        )
        cipher = AES.new(enc_key, AES.MODE_CTR, counter=ctr)
        plain_text += mic
        plain_text = bytes(cipher.encrypt(plain_text))

        return plain_text

    # flake8: noqa: C901
    def _process_start(self, msg: ProvisioningMessageSTART) -> None:
        # This is a START packet

        if msg.uid in self.data.keys() and self.data[msg.uid]["method"] == msg.method:
            logging.info("  - Sending Provisioning DATA for UID(%s).", msg.uid.hex())

            data_bytes = self.data.getCbor(msg.uid)

            if msg.method == ProvisioningMethod.UNSECURED:
                key_idx = 0
            else:
                key_idx = 1
                data_bytes = self._encrypt_packet(msg.uid, msg.iv, data_bytes)

            data_pkt = ProvisioningMessageDATA(
                self.session_id[1],
                self.session_id[2],
                self.counter,
                data_bytes,
                key_index=key_idx,
            ).payload
            logging.debug(" - Provisioning DATA packet: %s", "".join("{:02X}".format(x) + " " for x in data_pkt))

            res = self._send_packet(data_pkt)
            while True:
                if res is GatewayResultCode.GW_RES_OK:
                    logging.info("  - DATA packet sent.")
                    self.state = ProvisioningStates.WAIT_RESPONSE
                    self._timer_start(self.timeout)
                    break
                else:
                    logging.debug("  - DATA packet not sent: res:{}.".format(res))

                self.retry -= 1
                if self.retry >= 0:
                    logging.warning("  - %s - Re-send DATA.", msg)
                    res = self._send_packet(data_pkt)

                else:
                    logging.error("  - %s - Too many retry - Provisioning FAILURE.", msg)
                    self._timer_cancel()
                    self.status = ProvisioningStatus.ERROR_SENDING_DATA
                    return

        else:
            self.status = ProvisioningStatus.ERROR_NOT_AUTHORIZED

            if msg.uid not in self.data.keys():
                reason = ProvisioningNackReason.NOT_AUTHORIZED
            else:
                reason = ProvisioningNackReason.METHOD_NOT_SUPPORTED

            logging.error(
                " - UID(%s) not in whitelist (or method not supported) - Send NACK (%s).",
                msg.uid,
                reason,
            )

            res = self._send_packet(ProvisioningMessageNACK(self.session_id[1], self.session_id[2], reason).payload)
            while True:
                if res is GatewayResultCode.GW_RES_OK:
                    logging.info("  - NACK sent successfully, Provisioning FAILURE.")
                    self.status = ProvisioningStatus.ERROR_NOT_AUTHORIZED
                    if self._timer is not None:
                        self._timer.cancel()
                    break

                self.retry -= 1
                if self.retry >= 0:
                    logging.warning("  - Error sending NACK - Re-send NACK.")
                    res = self._send_packet(ProvisioningMessageNACK(self.session_id[1], self.session_id[2], reason).payload)
                else:
                    logging.error("  - Error sending NACK - Too many retry - Provisioning FAILURE.")
                    if self._timer is not None:
                        self._timer.cancel()
                    self.status = ProvisioningStatus.ERROR_SENDING_NACK

    def _state_idle(self, event: ProvisioningEventPacketReceived) -> None:
        logging.info("%s State IDLE:", str(self))

        if event.type == "packet_rxd" and event.msg.msg_type == ProvisioningMessageTypes.START:
            logging.info("  - Received START packet.")
            self._update_origin(event.msg)
            # Ignore type warning as we already checked the message type
            self._process_start(event.msg)  # type: ignore
        else:
            logging.error("  - Received packet is not a START packet - Provisioning FAILURE.")
            self._timer_cancel()
            self.status = ProvisioningStatus.ERROR_NOT_START

    def _state_wait_response(self, event: ProvisioningEventPacketReceived) -> None:
        logging.info("%s State Wait Node Response:", str(self))

        if event.type == "packet_rxd":
            self._update_origin(event.msg)
            if event.msg.msg_type == ProvisioningMessageTypes.START:
                logging.warning("  - START packet (re)received" " - Re-send DATA.")
                # Ignore type warning as we already checked the message type
                self._process_start(event.msg)  # type: ignore
                self._timer_start(self.timeout)

            elif event.msg.msg_type == ProvisioningMessageTypes.DATA_ACK:
                logging.info("  - ACK received, Provisioning SUCCESS.")
                self._timer_cancel()
                self.status = ProvisioningStatus.SUCCESS

            elif event.msg.msg_type == ProvisioningMessageTypes.NACK:
                # Ignore type warning as we already checked the message type
                logging.info("  - NACK received (%s)," " Provisioning FAILURE.", event.msg.reason)  # type: ignore
                self._timer_cancel()
                self.status = ProvisioningStatus.ERROR_NACK_RECEIVED
        elif event.type == "timeout":
            logging.error("  - No response from Node, Provisioning FAILURE.")
            self._timer_cancel()
            self.status = ProvisioningStatus.ERROR_NO_RESPONSE

    def run(self) -> None:

        while self.status == ProvisioningStatus.ONGOING:
            try:
                event = self.event_q.get(block=True)
            except queue.Empty:
                continue

            logging.debug("%s Event : %s", str(self), event.type)

            # IDLE
            if self.state == ProvisioningStates.IDLE:
                # Ignore type warning as we already checked the event type
                self._state_idle(event)  # type: ignore

            # WAIT NODE RESPONSE
            elif self.state == ProvisioningStates.WAIT_RESPONSE:
                # Ignore type warning as we already checked the event type
                self._state_wait_response(event)  # type: ignore

            else:
                logging.error("%s Invalid state - Provisioning FAILURE.", str(self))
                self.status = ProvisioningStatus.ERROR_INVALID_STATE

        self.finish_cb(self.session_id, self.status)
