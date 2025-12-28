
# enum for message types

from enum import Enum
class MessageType(Enum):
    # Hub-related messages
    HUB_PROPERTIES = 0x01  # Set or retrieve standard Hub Property information
    HUB_ACTIONS = 0x02  # Perform actions on connected hub
    HUB_ALERTS = 0x03  # Subscribe or retrieve Hub alerts
    HUB_ATTACHED_IO = 0x04  # Transmitted upon Hub detection of attached I/O
    GENERIC_ERROR_MESSAGES = 0x05  # Generic Error Messages from the Hub
    HW_NETWORK_COMMANDS = 0x08  # Commands used for H/W Networks
    FW_UPDATE_BOOT_MODE = 0x10  # Set the Hub in a special Boot Loader mode
    FW_UPDATE_LOCK_MEMORY = 0x11  # Locks the memory
    FW_UPDATE_LOCK_STATUS_REQUEST = 0x12  # Request the Memory Locking State
    FW_LOCK_STATUS = 0x13  # Answer to the F/W Lock Status Request

    # Port-related messages
    PORT_INFORMATION_REQUEST = 0x21  # Request Port information
    PORT_MODE_INFORMATION_REQUEST = 0x22  # Request Port Mode information
    PORT_INPUT_FORMAT_SETUP_SINGLE = 0x41  # Setup input format for single mode
    PORT_INPUT_FORMAT_SETUP_COMBINED = 0x42  # Setup input format for multiple modes (CombinedMode)
    PORT_INFORMATION = 0x43  # Response to Port Information Request (0x21)
    PORT_MODE_INFORMATION = 0x44  # Response to Port Mode Information Request (0x22)
    PORT_VALUE_SINGLE = 0x45  # Value update for single Port Mode (reply to 0x21)
    PORT_VALUE_COMBINED = 0x46  # Value update for multiple Port Modes in combination (CombinedMode) (reply to 0x21)
    PORT_INPUT_FORMAT_SINGLE = 0x47  # Response to Port Input Format Setup (Single) (0x41)
    PORT_INPUT_FORMAT_COMBINED = 0x48  # Response to Port Input Format Setup (CombinedMode) (0x42)

    # Output commands
    PORT_OUTPUT_COMMAND = 0x81  # Output command to a port
    PORT_OUTPUT_COMMAND_FEEDBACK = 0x82  # Feedback from output command

class MessageHeader:
    def __init__(self, message_type: MessageType, len: int):
        self.message_type = message_type
        self.length = len
        self.hub_id = 0

    @classmethod
    def from_bytes(cls, bytes):
        # Assuming the first byte is the length, second is hub ID, and third is message type
        return cls(MessageType(bytes[2]), bytes[0])

    def __str__(self):
        return f"MessageHeader(type={str(self.message_type)}, length={self.length})"

    def __repr__(self):
        return self.__str__()

    def bytes(self):
        # TODO: 2-byte encoding for length greater than 128
        return bytes([self.length, self.hub_id, self.message_type.value])

if __name__ == "__main__":
    # Example usage
    header = MessageHeader(MessageType.HUB_PROPERTIES, 5)
    print(header)
    print(header.bytes())
    print(MessageHeader.from_bytes(header.bytes()))

    raw = b'\x05\x00\x05\x01\x05.\x00\x00\x10\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'
    print(f"decoding {raw}")
    print(MessageHeader.from_bytes(raw[0:3]))