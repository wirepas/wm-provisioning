"""
    Provisioning message
    ===================

    .. Copyright:
        Copyright 2021 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""

from enum import IntEnum


class ProvisioningMessageException(Exception):
    """
    Wirepas Provisioning message generic Exception
    """


class ProvisioningMessageTypes(IntEnum):
    """ Provisioning message types """

    START = 1
    DATA = 2
    DATA_ACK = 3
    NACK = 4


class ProvisioningMethod(IntEnum):
    """ Provisioning methods """

    UNSECURED = 0
    SECURED = 1


class ProvisioningNackReason(IntEnum):
    """ Provisioning nack reason """

    NOT_AUTHORIZED = 0
    METHOD_NOT_SUPPORTED = 1
    INVALID_DATA = 2
    INVALID_KEY = 3


class ProvisioningMessage:
    def __init__(
        self,
        msg_type,
        node_address,
        session_id,
        source_address=None,
        gw_id=None,
        sink_id=None,
        tx_time=None,
    ):

        try:
            self.msg_type = ProvisioningMessageTypes(msg_type)
        except ValueError:
            raise ProvisioningMessageException("Message type is invalid.")
        self.node_address = node_address
        self.session_id = session_id
        self.source_address = source_address
        self.gw_id = gw_id
        self.sink_id = sink_id
        self.tx_time = tx_time

    @property
    def msg_id(self):
        return (self.source_address, self.node_address, self.session_id)

    def __str__(self):
        return "".join(
            [
                "[{:08X}".format(self.source_address),
                ", ",
                "".join("{:02X}".format(x) for x in self.node_address),
                ", {:02X}".format(self.session_id),
                "]",
            ]
        )

    @property
    def payload(self):
        """ Implement how to serialize child Event classes """
        return b"".join([bytes([self.msg_type]), self.node_address, bytes([self.session_id])])

    @classmethod
    def from_message(cls, message):
        raise NotImplementedError()


class ProvisioningMessageSTART(ProvisioningMessage):
    def __init__(
        self,
        node_address,
        session_id,
        method,
        iv,
        uid,
        source_address=None,
        gw_id=None,
        sink_id=None,
        tx_time=None,
    ):

        try:
            self.method = ProvisioningMethod(method)
        except ValueError:
            raise ProvisioningMessageException("Provisioning method is invalid.")

        if len(iv) == 16:
            self.iv = iv
        else:
            raise ProvisioningMessageException("Invalid IV length (%s instead of 16).", len(iv))
        if len(uid) > 0:
            self.uid = uid
        else:
            raise ProvisioningMessageException("UID length too small.")

        super(ProvisioningMessageSTART, self).__init__(
            msg_type=ProvisioningMessageTypes.START,
            node_address=node_address,
            session_id=session_id,
            source_address=source_address,
            gw_id=gw_id,
            sink_id=sink_id,
            tx_time=tx_time,
        )

    @property
    def payload(self):
        """ Implement how to serialize child Event classes """
        return b"".join([super().payload, bytes([self.method]), self.iv, self.uid])

    @classmethod
    def from_message(cls, message):
        # TODO check data_payload min/max length

        try:
            msg_type = ProvisioningMessageTypes(message.data_payload[0])

            if msg_type != ProvisioningMessageTypes.START:
                raise ProvisioningMessageException("Message type is not START.")
        except ValueError:
            raise ProvisioningMessageException("Message type is invalid.")

        try:
            method = ProvisioningMethod(message.data_payload[6])
        except ValueError:
            raise ProvisioningMessageException("Provisioning method is invalid.")

        return cls(
            node_address=message.data_payload[1:5],
            session_id=message.data_payload[5],
            method=method,
            iv=message.data_payload[7:23],
            uid=message.data_payload[23:],
            source_address=message.source_address,
            gw_id=message.gw_id,
            sink_id=message.sink_id,
            tx_time=message.rx_time_ms_epoch - message.travel_time_ms,
        )


class ProvisioningMessageDATA(ProvisioningMessage):
    def __init__(
        self,
        node_address,
        session_id,
        counter,
        data,
        key_index=1,  # Only factory key is supported.
        mic=bytes(),
        source_address=None,
        gw_id=None,
        sink_id=None,
        tx_time=None,
    ):

        self.key_index = key_index
        self.counter = counter

        if len(data) > 0:
            self.data = data
        else:
            raise ProvisioningMessageException(
                "Provisioning data length too small."
            )

        if len(mic) == 0 or len(mic) == 5:
            self.mic = mic
        else:
            raise ProvisioningMessageException("Invalid MIC length (%s instead of 5).", len(mic))

        super(ProvisioningMessageDATA, self).__init__(
            msg_type=ProvisioningMessageTypes.DATA,
            node_address=node_address,
            session_id=session_id,
            source_address=source_address,
            gw_id=gw_id,
            sink_id=sink_id,
            tx_time=tx_time,
        )

    @property
    def payload(self):
        """ Implement how to serialize child Event classes """
        return b"".join(
            [
                super().payload,
                bytes([self.key_index]),
                (self.counter).to_bytes(2, byteorder="little"),
                self.data,
                self.mic,
            ]
        )

    @classmethod
    def from_message(cls, message):

        try:
            msg_type = ProvisioningMessageTypes(message.data_payload[0])

            if msg_type != ProvisioningMessageTypes.DATA:
                raise ProvisioningMessageException("Message type is not DATA.")

        except ValueError:
            raise ProvisioningMessageException("Message type is invalid.")

        counter = int.from_bytes(
            message.payload[7:9], byteorder="little", signed=True
        )

        return cls(
            node_address=message.data_payload[1:5],
            session_id=message.data_payload[5],
            key_index=message.data_payload[6],
            counter=counter,
            data=message.data_payload[9:-6],
            mic=message.data_payload[:-5],
            source_address=message.source_address,
            gw_id=message.gw_id,
            sink_id=message.sink_id,
            tx_time=message.rx_time_ms_epoch - message.travel_time_ms,
        )


class ProvisioningMessageDATA_ACK(ProvisioningMessage):
    def __init__(
        self,
        node_address,
        session_id,
        source_address=None,
        gw_id=None,
        sink_id=None,
        tx_time=None,
    ):

        super(ProvisioningMessageDATA_ACK, self).__init__(
            msg_type=ProvisioningMessageTypes.DATA_ACK,
            node_address=node_address,
            session_id=session_id,
            source_address=source_address,
            gw_id=gw_id,
            sink_id=sink_id,
            tx_time=tx_time,
        )

    @property
    def payload(self):
        """ Implement how to serialize child Event classes """
        return super().payload

    @classmethod
    def from_message(cls, message):
        try:
            msg_type = ProvisioningMessageTypes(message.data_payload[0])

            if msg_type != ProvisioningMessageTypes.DATA_ACK:
                raise ProvisioningMessageException("Message type is not DATA_ACK.")
        except ValueError:
            raise ProvisioningMessageException("Message type is invalid.")

        return cls(
            node_address=message.data_payload[1:5],
            session_id=message.data_payload[5],
            source_address=message.source_address,
            gw_id=message.gw_id,
            sink_id=message.sink_id,
            tx_time=message.rx_time_ms_epoch - message.travel_time_ms,
        )


class ProvisioningMessageNACK(ProvisioningMessage):
    def __init__(
        self,
        node_address,
        session_id,
        reason,
        source_address=None,
        gw_id=None,
        sink_id=None,
        tx_time=None,
    ):

        try:
            self.reason = ProvisioningNackReason(reason)
        except ValueError:
            raise ProvisioningMessageException(
                "Provisioning NACK reason is invalid."
            )

        super(ProvisioningMessageNACK, self).__init__(
            msg_type=ProvisioningMessageTypes.NACK,
            node_address=node_address,
            session_id=session_id,
            source_address=source_address,
            gw_id=gw_id,
            sink_id=sink_id,
            tx_time=tx_time,
        )

    @property
    def payload(self):
        """ Implement how to serialize child Event classes """
        return b"".join([super().payload, bytes([self.reason])])

    @classmethod
    def from_message(cls, message):
        try:
            msg_type = ProvisioningMessageTypes(message.data_payload[0])

            if msg_type != ProvisioningMessageTypes.NACK:
                raise ProvisioningMessageException("Message type is not NACK.")

        except ValueError:
            raise ProvisioningMessageException("Message type is invalid.")

        try:
            reason = ProvisioningNackReason(message.data_payload[6])
        except ValueError:
            raise ProvisioningMessageException(
                "Provisioning nack reason is invalid."
            )

        return cls(
            node_address=message.data_payload[1:5],
            session_id=message.data_payload[5],
            reason=reason,
            source_address=message.source_address,
            gw_id=message.gw_id,
            sink_id=message.sink_id,
            tx_time=message.rx_time_ms_epoch - message.travel_time_ms,
        )


class ProvisioningMessageFactory(object):
    """
    MessageManager

    """

    _type = dict()
    _type[ProvisioningMessageTypes.START] = ProvisioningMessageSTART
    _type[ProvisioningMessageTypes.DATA] = ProvisioningMessageDATA
    _type[ProvisioningMessageTypes.DATA_ACK] = ProvisioningMessageDATA_ACK
    _type[ProvisioningMessageTypes.NACK] = ProvisioningMessageNACK

    def __init__(self):

        super(ProvisioningMessageFactory, self).__init__()

    @staticmethod
    def map(message):
        try:
            return ProvisioningMessageFactory._type[ProvisioningMessageTypes(message.data_payload[0])].from_message(message)
        except (KeyError, ValueError):
            raise ProvisioningMessageException("Not a provisioning message.")
