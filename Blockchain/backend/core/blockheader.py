from Blockchain.backend.util.util import hash256, little_endian_to_int, int_to_little_endian

class BlockHeader:
    def __init__(self, version, prev_block_hash, merkle_root, timestamp, bits, nonce=0):
        self.version = version

        if isinstance(prev_block_hash, str):
            self.prev_block_hash = bytes.fromhex(prev_block_hash)
        else:
            self.prev_block_hash = prev_block_hash

        if isinstance(merkle_root, str):
            self.merkle_root = bytes.fromhex(merkle_root)
        else:
            self.merkle_root = merkle_root

        self.timestamp = timestamp

        if isinstance(bits, str):
            self.bits = bytes.fromhex(bits)
        elif isinstance(bits, int):
            self.bits = int_to_little_endian(bits, 4)
        else:
            self.bits = bits

        self.nonce = nonce
        self.block_hash = None

    def hash(self):
        s = b''
        s += self.version.to_bytes(4, 'little')
        s += self.prev_block_hash
        s += self.merkle_root
        s += self.timestamp.to_bytes(4, 'little')
        s += self.bits
        s += self.nonce.to_bytes(4, 'little')
        return hash256(s)[::-1]

    def to_dict(self):
        return {
            'version': self.version,
            'prev_block_hash': self.prev_block_hash.hex(),
            'merkle_root': self.merkle_root.hex(),
            'timestamp': self.timestamp,
            'bits': self.bits.hex(),
            'nonce': self.nonce,
            'block_hash': self.block_hash.hex() if isinstance(self.block_hash, bytes) else self.block_hash
        }

    @classmethod
    def from_dict(cls, data):

        return cls(
            version=data['version'],
            prev_block_hash=data['prev_block_hash'],
            merkle_root=data['merkle_root'],
            timestamp=data['timestamp'],
            bits=data['bits'],
            nonce=data['nonce']
        )

    def mine(self, target):
        print(f"DEBUG (mine): Starting mining loop. Initial nonce: {self.nonce}")
        print(f"DEBUG (mine): Target: {hex(target)}")
        current_hash_int = int(self.hash().hex(), 16)

        while current_hash_int >= target:
            self.nonce += 1
            current_hash_int = int(self.hash().hex(), 16)

        self.block_hash = self.hash()
        print(f"Mining Finished. Nonce: {self.nonce}, Final Hash: {self.block_hash.hex()}")
        print(f"DEBUG: Mining beendet. Nonce: {self.nonce}, Block Hash: {self.block_hash.hex()}")