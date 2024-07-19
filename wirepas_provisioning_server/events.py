"""
    Provisioning events
    ===================

    .. Copyright:
        Copyright 2021 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""
from .message import ProvisioningMessage


class ProvisioningEvent(object):
    def __init__(self) -> None:
        super(ProvisioningEvent, self).__init__()
        self.type = "generic"


class ProvisioningEventTimeout(ProvisioningEvent):
    def __init__(self) -> None:
        super(ProvisioningEventTimeout, self).__init__()
        self.type = "timeout"


class ProvisioningEventPacketReceived(ProvisioningEvent):
    def __init__(self, msg: ProvisioningMessage) -> None:
        super(ProvisioningEventPacketReceived, self).__init__()
        self.type = "packet_rxd"
        self.msg = msg
