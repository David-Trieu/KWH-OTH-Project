import sys
sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from backend.core.block import Block
from backend.core.blockheader import BlockHeader
from backend.util.util import hash256
import time
import json

ZERO_HASH = '0' * 64
VERSION = 1

class Blockchain:
    def __init__(self):
        self.chain = []
        self.GenesisBlock()

    def GenesisBlock(self):
        BlockHeight = 0
        prevBlockHash = ZERO_HASH
        self.addBlock(BlockHeight, prevBlockHash)

    def addBlock(self, BlockHeight,prevBlockHash):
        timestamp = int(time.time())
        Transaction = f"Sent Block #{BlockHeight}"
        merkleRoot = hash256(Transaction.encode()).hex()
        bits = 'ffff001f'
        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, bits)
        blockHeader.mine()
        self.chain.append(Block(BlockHeight,1,blockHeader.__dict__,1,Transaction).__dict__)
        print(json.dumps(self.chain, indent= 4))

    def main(self):
        for i in range(4):
            lastBlock = self.chain[::-1]
            BlockHeight = lastBlock[0]["Height"] + 1
            prevBlockHash = lastBlock[0]['BlockHeader']["blockHash"]
            self.addBlock(BlockHeight, prevBlockHash)

if __name__ == "__main__":
    blockchain = Blockchain()
    blockchain.main()