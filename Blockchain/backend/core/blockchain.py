import sys
sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256, merkle_root
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx
from multiprocessing import Process, Manager
from Blockchain.frontend.run import main

import time

ZERO_HASH = '0' * 64
VERSION = 1

class Blockchain:
    def __init__(self, utxos, MemPool):
        self.utxos = utxos
        self.MemPool = MemPool

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

    #Keep Track of all unspent Transactions in cache memory for fast retrival
    def store_uxtos_in_cache(self, Transaction):
        self.utxos[Transaction.TxId] = Transaction

    def read_transaction_from_memorypool(self):
        self.TxIds = []
        self.addTransactionsInBlock = []

        for tx in self.MemPool:
            self.TxIds.append(bytes.fromhex(tx))
            self.addTransactionsInBlock.append(self.MemPool[tx])

    def convert_to_json(self):
        self.TxJson = []
        for tx in self.addTransactionsInBlock:
            self.TxJson.append(tx.to_dict())

    def addBlock(self, BlockHeight,prevBlockHash):
        self.read_transaction_from_memorypool()
        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()

        self.TxIds.insert(0,bytes.fromhex(coinbaseTx.TxId))
        self.addTransactionsInBlock.insert(0,coinbaseTx)

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()
        bits = 'ffff001f'
        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, bits)
        blockHeader.mine()

        self.store_uxtos_in_cache(coinbaseTx)
        self.convert_to_json()

        print(f"Block Height {BlockHeight} mined successfully with Nonce value of {blockHeader.nonce}")
        self.safeInDB([Block(BlockHeight,1,blockHeader.__dict__,1,self.TxJson).__dict__])

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
    with Manager() as manager:
        utxos = manager.dict()
        MemPool = manager.dict()

        webapp = Process(target = main, args = (utxos, MemPool))
        webapp.start()

        blockchain = Blockchain(utxos, MemPool)
        blockchain.main()