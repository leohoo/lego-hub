from message_header import MessageHeader, MessageType
from io_device_type import IODeviceType

class LegoMessage:
    def __init__(self, message_type, payload, length=None):
        self.header = MessageHeader(message_type, length or (3+len(payload)))
        self.payload = payload

    @classmethod
    def from_bytes(cls, bytes):
        # Assuming the first byte is the length, second is hub ID, and third is message type
        header = MessageHeader.from_bytes(bytes)

        payload = bytes[3:header.length]
        return cls(header.message_type, payload, header.length)

    def to_bytes(self):
        return self.header.bytes() + self.payload

    def __str__(self):
        return f"LegoMessage(type={str(self.header)}, payload={self.payload})"

    def parse(self):
        match self.header.message_type:
            case MessageType.HUB_ATTACHED_IO:
                parse_hub_attached_io(self.payload)
            case _:
                pass

        return self.payload

def parse_hub_attached_io(payload):
    # Assuming payload is a bytearray or bytes object
    if len(payload) < 2:
        raise ValueError("Payload too short for hub attached IO")

    port_id = payload[0]
    event = payload[1]

    iotype = payload[2:4]
    iotype = int.from_bytes(iotype, byteorder='little')

    hardware_revision = payload[4:8]
    software_revision = payload[8:12]

    port_id_a = payload[4]
    port_id_b = payload[5]

    print(f"Port ID: {port_id}, Event: {event}, 0x{iotype:x}: {str(IODeviceType(iotype))}, Hardware Revision: {hardware_revision}, Software Revision: {software_revision}, Port ID A: {port_id_a}, Port ID B: {port_id_b}")
    return {
        "port_id": port_id,
        "event": event,
        "io_type": iotype,
        "hardware_revision": hardware_revision,
        "software_revision": software_revision,
        "port_id_a": port_id_a,
        "port_id_b": port_id_b
    }