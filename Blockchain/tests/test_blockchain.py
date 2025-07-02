import pytest
import time
import datetime
import requests

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256, merkle_root, target_to_bits, int_to_little_endian, bytes_needed, \
    decode_base58, little_endian_to_int, encode_varint
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx, Tx, TxIn, TxOut
from Blockchain.backend.core.Script import Script

from Blockchain.backend.core.blockchain import Blockchain, ZERO_HASH, VERSION, INITIAL_TARGET, PRICE_MAX, PRICE_MIN, \
    EEG_UMLAGE_PRICE, MIN_TARGET_REDUCTION_FACTOR, MIN_ADJUSTED_TARGET, SMALL_EASIER_FACTOR, SLIGHTLY_EASIER_TARGET

REWARD = 50
MINER_ADDRESS = '1LWxEfevJUFv73hVGmqJ72ZwfqYv1GzMUk'


class DummyScript(Script):
    def __init__(self, cmds=None):
        super().__init__(cmds if cmds is not None else [])

    def serialize(self):
        return b'\x01\x02\x03'

    def to_dict(self):
        return {'cmds': [str(c) for c in self.cmds]}


@pytest.fixture
def empty_blockchain_instance():
    utxos_dict = {}
    mempool_dict = {}
    return Blockchain(utxos_dict, mempool_dict)


@pytest.fixture
def sample_tx_in():
    return TxIn(prev_tx=b'\x01' * 32, prev_index=0, script_sig=DummyScript())


@pytest.fixture
def sample_tx_out():
    return TxOut(amount=10000, script_pubkey=DummyScript())


@pytest.fixture
def sample_transaction(sample_tx_in, sample_tx_out):
    return Tx(
        version=VERSION,
        tx_ins=[sample_tx_in],
        tx_outs=[sample_tx_out],
        locktime=0,
        segwit=False
    )


def test_blockchain_initialization(empty_blockchain_instance):
    blockchain = empty_blockchain_instance
    assert blockchain.utxos == {}
    assert blockchain.MemPool == {}
    assert blockchain.current_target == INITIAL_TARGET
    assert blockchain.bits == target_to_bits(INITIAL_TARGET)
    assert blockchain.last_price_check_time == 0
    assert blockchain.price_check_interval == 3600
    assert blockchain.prevBlockHash == ZERO_HASH


def test_read_transaction_from_memorypool(empty_blockchain_instance, sample_transaction):
    blockchain = empty_blockchain_instance
    blockchain.MemPool[sample_transaction.id()] = sample_transaction

    blockchain.read_transaction_from_memorypool()

    assert len(blockchain.TxIds) == 1
    assert blockchain.TxIds[0].hex() == sample_transaction.id()
    assert len(blockchain.addTransactionsInBlock) == 1
    assert blockchain.addTransactionsInBlock[0] == sample_transaction
    assert len(blockchain.remove_spent_transactions) == 1
    assert blockchain.remove_spent_transactions[0][0] == sample_transaction.tx_ins[0].prev_tx
    assert blockchain.remove_spent_transactions[0][1] == sample_transaction.tx_ins[0].prev_index
    assert blockchain.Blocksize > 80


def test_calculate_fee(empty_blockchain_instance):
    blockchain = empty_blockchain_instance

    prev_tx_id_bytes = b'\xaa' * 32
    prev_tx_id_hex = prev_tx_id_bytes.hex()
    blockchain.utxos[prev_tx_id_hex] = Tx(
        version=VERSION, tx_ins=[], tx_outs=[TxOut(amount=50000, script_pubkey=DummyScript())], locktime=0
    )

    tx_in_paying = TxIn(prev_tx=prev_tx_id_bytes, prev_index=0, script_sig=DummyScript())
    tx_out_receiving = TxOut(amount=40000, script_pubkey=DummyScript())
    test_tx = Tx(version=VERSION, tx_ins=[tx_in_paying], tx_outs=[tx_out_receiving],
                 locktime=0)
    blockchain.MemPool[test_tx.id()] = test_tx

    blockchain.read_transaction_from_memorypool()
    blockchain.calculate_fee()

    assert blockchain.input_amount == 50000
    assert blockchain.output_amount == 40000
    assert blockchain.fee == 10000


def test_remove_spent_transactions(empty_blockchain_instance):
    blockchain = empty_blockchain_instance

    tx_id_multi_out = "1" * 64
    blockchain.utxos[tx_id_multi_out] = Tx(
        version=VERSION, tx_ins=[],
        tx_outs=[
            TxOut(amount=100, script_pubkey=DummyScript()),
            TxOut(amount=200, script_pubkey=DummyScript()),
            TxOut(amount=300, script_pubkey=DummyScript())
        ],
        locktime=0
    )

    spent_tx_id_bytes_1 = bytes.fromhex(tx_id_multi_out)
    blockchain.remove_spent_transactions = [[spent_tx_id_bytes_1, 0]]
    blockchain.remove_spent_Transactions()

    assert tx_id_multi_out in blockchain.utxos
    assert len(blockchain.utxos[tx_id_multi_out].tx_outs) == 2
    assert blockchain.utxos[tx_id_multi_out].tx_outs[
               0].amount == 200
    assert blockchain.utxos[tx_id_multi_out].tx_outs[1].amount == 300

    blockchain.remove_spent_transactions = [[spent_tx_id_bytes_1, 0]]
    blockchain.remove_spent_Transactions()

    assert tx_id_multi_out in blockchain.utxos
    assert len(blockchain.utxos[tx_id_multi_out].tx_outs) == 1
    assert blockchain.utxos[tx_id_multi_out].tx_outs[0].amount == 300

    blockchain.remove_spent_transactions = [[spent_tx_id_bytes_1, 0]]
    blockchain.remove_spent_Transactions()

    assert tx_id_multi_out not in blockchain.utxos


def test_remove_transactions_from_memorypool(empty_blockchain_instance, sample_transaction):
    blockchain = empty_blockchain_instance
    blockchain.MemPool[sample_transaction.id()] = sample_transaction

    blockchain.TxIds = []

    blockchain.TxIds.append(bytes.fromhex(sample_transaction.id()))

    assert len(blockchain.MemPool) == 1
    blockchain.remove_transactions_from_memorypool()
    assert len(blockchain.MemPool) == 0


def test_store_utxos_in_cache(empty_blockchain_instance, sample_transaction):
    blockchain = empty_blockchain_instance
    blockchain.addTransactionsInBlock = [sample_transaction]

    assert len(blockchain.utxos) == 0
    blockchain.store_uxtos_in_cache()
    assert len(blockchain.utxos) == 1
    assert sample_transaction.id() in blockchain.utxos
    assert blockchain.utxos[sample_transaction.id()] == sample_transaction


def test_convert_to_json(empty_blockchain_instance, sample_transaction):
    blockchain = empty_blockchain_instance
    blockchain.addTransactionsInBlock = [sample_transaction]

    blockchain.TxJson = []

    blockchain.convert_to_json()

    assert hasattr(blockchain, 'TxJson')
    assert len(blockchain.TxJson) == 1
    assert isinstance(blockchain.TxJson[0], dict)
    assert 'TxId' in blockchain.TxJson[0]
    assert blockchain.TxJson[0]['TxId'] == sample_transaction.id()


def test_adjust_target_based_on_price_logic_only(empty_blockchain_instance):
    blockchain = empty_blockchain_instance
    blockchain.last_price_check_time = 0

    original_get_price_method = blockchain.get_current_electricity_price
    try:
        blockchain.get_current_electricity_price = lambda: 5.0
        blockchain.adjust_target_based_on_price()
        assert SLIGHTLY_EASIER_TARGET >= blockchain.current_target >= INITIAL_TARGET
        assert blockchain.current_target > INITIAL_TARGET
        assert blockchain.last_price_check_time > 0

        blockchain.current_target = INITIAL_TARGET
        blockchain.last_price_check_time = 0
        blockchain.get_current_electricity_price = lambda: 200.0
        blockchain.adjust_target_based_on_price()
        assert INITIAL_TARGET >= blockchain.current_target >= MIN_ADJUSTED_TARGET
        assert blockchain.current_target < INITIAL_TARGET

        old_target = blockchain.current_target
        blockchain.last_price_check_time = 0
        blockchain.get_current_electricity_price = lambda: None
        blockchain.adjust_target_based_on_price()
        assert blockchain.current_target == old_target

        blockchain.last_price_check_time = time.time()
        old_target = blockchain.current_target
        blockchain.get_current_electricity_price = lambda: 10.0
        blockchain.adjust_target_based_on_price()
        assert blockchain.current_target == old_target

    finally:
        blockchain.get_current_electricity_price = original_get_price_method