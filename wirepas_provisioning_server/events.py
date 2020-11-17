"""
    Provisioning events
    ===================

    .. Copyright:
        Copyright 2021 Wirepas Ltd under Apache License, Version 2.0.
        See file LICENSE for full license details.
"""


class ProvisioningEvent(object):
    def __init__(self):
        super(ProvisioningEvent, self).__init__()
        self.type = "generic"


class ProvisioningEventTimeout(ProvisioningEvent):
    def __init__(self):
        super(ProvisioningEventTimeout, self).__init__()
        self.type = "timeout"


class ProvisioningEventPacketReceived(ProvisioningEvent):
    def __init__(self, msg):
        super(ProvisioningEventPacketReceived, self).__init__()
        self.type = "packet_rxd"
        self.msg = msg
