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
    def store_uxtos_in_cache(self):
        for tx in self.addTransactionsInBlock:
            print(f"Transaction added {tx.TxId}")
            self.utxos[tx.TxId]= tx

    def remove_spent_Transactions(self):
        for txId_index in self.remove_spent_transactions:
            if txId_index[0].hex() in self.utxos:

                if len(self.utxos[txId_index[0].hex()].tx_outs) < 2:
                    print(f"Spent Transaction removed {txId_index[0].hex()}")
                    del self.utxos[txId_index[0].hex()]
                else:
                    prev_trans = self.utxos[txId_index[0].hex()]
                    self.utxos[txId_index[0].hex()] = prev_trans.tx_outs.pop(txId_index[1])

    def read_transaction_from_memorypool(self):
        self.TxIds = []
        self.addTransactionsInBlock = []
        self.remove_spent_transactions = []

        for tx in self.MemPool:
            self.TxIds.append(bytes.fromhex(tx))
            self.addTransactionsInBlock.append(self.MemPool[tx])

            for spent in self.MemPool[tx].tx_ins:
                self.remove_spent_transactions.append([spent.prev_tx, spent.prev_index])

    def remove_transactions_from_memorypool(self):
        for tx in self.TxIds:
            if tx.hex() in self.MemPool:
                del self.MemPool[tx.hex()]

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

        self.remove_spent_Transactions()
        self.remove_transactions_from_memorypool()
        self.store_uxtos_in_cache()
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