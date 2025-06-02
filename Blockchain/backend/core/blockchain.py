import sys
sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx

import time

ZERO_HASH = '0' * 64
VERSION = 1

class Blockchain:
    def __init__(self):
        pass

    def safeInDB(self,block):
        db = BlockchainDB()
        db.write(block)

    def getLastBlock(self):
        db = BlockchainDB()
        return db.lastBlock()

    def GenesisBlock(self):
        BlockHeight = 0
        prevBlockHash = ZERO_HASH
        self.addBlock(BlockHeight, prevBlockHash)

    def addBlock(self, BlockHeight,prevBlockHash):
        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()
        merkleRoot = coinbaseTx.TxId
        bits = 'ffff001f'
        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, bits)
        blockHeader.mine()
        print(f"Block Height {BlockHeight} mined successfully with Nonce value of {blockHeader.nonce}")
        self.safeInDB([Block(BlockHeight,1,blockHeader.__dict__,1,coinbaseTx.to_dict()).__dict__])

    def main(self):
        lastBlock = self.getLastBlock()
        if lastBlock is None:
            self.GenesisBlock()
        while True:
            lastBlock = self.getLastBlock()
            BlockHeight = lastBlock["Height"] + 1
            prevBlockHash = lastBlock['BlockHeader']["blockHash"]
            self.addBlock(BlockHeight, prevBlockHash)

if __name__ == "__main__":
    blockchain = Blockchain()
    blockchain.main()