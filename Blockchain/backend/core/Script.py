from Blockchain.backend.util.util import int_to_little_endian, encode_varint
from Blockchain.backend.core.EllepticCurve.op import OP_CODE_FUNCTION # Note: Typo 'EllepticCurve' -> 'EllipticCurve'?

class Script:
    def __init__(self, cmds=None):
        if cmds is None:
            self.cmds = []
        else:
            self.cmds = cmds

    @classmethod
    def from_dict(cls, data):
        cmds = []

        for cmd_item in data.get('cmds', []):
            if isinstance(cmd_item, str):
                cmds.append(bytes.fromhex(cmd_item))
            elif isinstance(cmd_item, int):
                cmds.append(cmd_item)
            else:
                cmds.append(cmd_item)

        return cls(cmds=cmds)

    def to_dict(self):
        serialized_cmds = []
        for cmd in self.cmds:
            if isinstance(cmd, bytes):
                serialized_cmds.append(cmd.hex())
            elif isinstance(cmd, int):
                serialized_cmds.append(cmd)
            else:
                serialized_cmds.append(cmd)

        return {
            'cmds': serialized_cmds
        }


    def __add__(self, other):
        return Script(self.cmds + other.cmds)

    def serialize(self):
        result = b""
        for cmd in self.cmds:
            if type(cmd) == int:
                result += int_to_little_endian(cmd, 1)
            else:
                length = len(cmd)
                if length < 75:
                    result += int_to_little_endian(length, 1)
                elif length >= 75 and length < 0x100:
                    result += int_to_little_endian(76, 1)
                    result += int_to_little_endian(length, 1)
                elif length >= 0x100 and length <= 520:
                    result += int_to_little_endian(77, 1)
                    result += int_to_little_endian(length, 2)
                else:
                    raise ValueError("too long cmd")

                result += cmd
        total = len(result)
        return encode_varint(total) + result

    def evaluate(self, z):
        cmds = self.cmds[:]
        stack = []

        while len(cmds) > 0:
            cmd = cmds.pop(0)

            if type(cmd) == int:
                operation = OP_CODE_FUNCTION[cmd]
                if cmd == 172:
                    if not operation(stack, z):
                        print(f"Error in Signature Verification")
                        return False

                elif not operation(stack):
                    print(f"Error in Signature Verification")
                    return False
            else:
                stack.append(cmd)
        return True

    @classmethod
    def p2pkh_script(cls, h160):
        OP_DUP = 0x76
        OP_HASH160 = 0xa9
        OP_EQUALVERIFY = 0x88
        OP_CHECKSIG = 0xac
        return cls([OP_DUP, OP_HASH160, h160, OP_EQUALVERIFY, OP_CHECKSIG])