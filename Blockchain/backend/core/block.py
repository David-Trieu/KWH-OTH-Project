from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.core.Tx import Tx

class Block:
    def __init__(self, height, size, block_header, num_transactions, transactions):
        self.height = height
        self.size = size
        if isinstance(block_header, dict):
            self.block_header = BlockHeader.from_dict(block_header)
        else:
            self.block_header = block_header

        self.num_transactions = num_transactions
        self.transactions = transactions

    @classmethod
    def from_dict(cls, data):
        transactions_list_of_objects = [Tx.from_dict(tx_data) for tx_data in data['Txs']]

        new_block = cls(

            height=data.get('Height', 0),
            size=data.get('Size', 80),
            block_header=data['BlockHeader'],
            num_transactions=data.get('NumTransactions', 0),
            transactions=transactions_list_of_objects
        )
        return new_block

    def to_dict(self):
        block_dict = {}
        block_dict['Height'] = self.height
        block_dict['Size'] = self.size
        block_dict['BlockHeader'] = self.block_header.to_dict()
        block_dict['NumTransactions'] = self.num_transactions
        block_dict['Txs'] = [tx_obj.to_dict() for tx_obj in self.transactions]
        return block_dict