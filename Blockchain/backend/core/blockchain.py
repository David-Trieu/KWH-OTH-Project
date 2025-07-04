import sys
import time
import requests
import datetime
from multiprocessing import Process, Manager

sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256, merkle_root, target_to_bits
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx, Tx
from Blockchain.frontend.run import main

ZERO_HASH = '0' * 64
VERSION = 1

INITIAL_TARGET = 0x00000FFFF0000000000000000000000000000000000000000000000000000000
PRICE_MIN = 0

EEG_EINSPEISE_VERGÜTUNG = 12.60


SMALL_EASIER_FACTOR = 0.2
SLIGHTLY_EASIER_TARGET = int(INITIAL_TARGET * (1 + SMALL_EASIER_FACTOR))

def function1(manager_instance: Manager):

    utxos_dict = manager_instance.dict()
    db = BlockchainDB()
    all_blocks_data = db.read()

    if not all_blocks_data:
        print("DEBUG: Keine Blöcke in der Datenbank gefunden. UTXO-Cache bleibt leer.")
        return utxos_dict

    spent_outputs = set()

    for block_data in all_blocks_data:
        block = Block.from_dict(block_data)

        for tx in block.transactions:
            for tx_in in tx.tx_ins:
                spent_outputs.add((tx_in.prev_tx.hex(), tx_in.prev_index))

    for block_data in all_blocks_data:
        block = Block.from_dict(block_data)

        for tx in block.transactions:
            tx_id_hex = tx.id()

            filtered_tx_outs = []
            for i, tx_out in enumerate(tx.tx_outs):
                if (tx_id_hex, i) not in spent_outputs:
                    filtered_tx_outs.append(tx_out)

            if filtered_tx_outs:
                temp_tx = Tx(tx.version, tx.tx_ins, filtered_tx_outs, tx.locktime, tx.segwit)
                utxos_dict[tx_id_hex] = temp_tx
            else:
                print(f"DEBUG: Alle Outputs von Transaktion {tx_id_hex} sind verbraucht.")

    return utxos_dict


def function2(manager_instance: Manager):
    return manager_instance.dict()

class Blockchain:
    def __init__(self, utxos, MemPool):
        self.utxos = utxos
        self.MemPool = MemPool
        self.current_target = INITIAL_TARGET
        self.bits = target_to_bits(INITIAL_TARGET)
        self.last_price_check_time = 0
        self.price_check_interval = 3600
        self.prevBlockHash = '0000000000000000000000000000000000000000000000000000000000000000'  # For Genesis

    def safeInDB(self, block):
        db = BlockchainDB()
        db.write(block)

    def getLastBlock(self):
        db = BlockchainDB()
        return db.lastBlock()

    def GenesisBlock(self):
        BlockHeight = 0
        prevBlockHash = ZERO_HASH
        self.addBlock(BlockHeight, self.prevBlockHash)

    def store_uxtos_in_cache(self):
        for tx in self.addTransactionsInBlock:
            tx_id_hex = tx.id()
            self.utxos[tx_id_hex] = tx

    def remove_spent_Transactions(self):
        utxos_to_delete_from_cache = []
        spent_transactions_to_process = list(self.remove_spent_transactions)
        for txId_index in spent_transactions_to_process:
            prev_tx_id_bytes = txId_index[0]
            prev_tx_id_hex = prev_tx_id_bytes.hex()
            prev_tx_out_index = txId_index[1]

            if prev_tx_id_hex in self.utxos:
                prev_trans_utxo = self.utxos[prev_tx_id_hex]

                if 0 <= prev_tx_out_index < len(prev_trans_utxo.tx_outs):
                    spent_output_amount = prev_trans_utxo.tx_outs[prev_tx_out_index].amount

                    new_tx_outs = [
                        tx_out for i, tx_out in enumerate(prev_trans_utxo.tx_outs)
                        if i != prev_tx_out_index
                    ]

                    if not new_tx_outs:
                        utxos_to_delete_from_cache.append(prev_tx_id_hex)
                    else:
                        prev_trans_utxo.tx_outs = new_tx_outs
                        self.utxos[prev_tx_id_hex] = prev_trans_utxo

                else:
                    print(
                        f"WARNING: PrevIndex {prev_tx_out_index} ist für TxId {prev_tx_id_hex} ungültig (bereits ausgegeben?). Überspringe.")
            else:
                print(
                    f"WARNING: Vorherige Transaktion {prev_tx_id_hex} für Input nicht in UTXOs gefunden. Könnte schon ausgegeben sein oder Fehler.")

        for tx_id_hex in utxos_to_delete_from_cache:
            if tx_id_hex in self.utxos:
                del self.utxos[tx_id_hex]

    def read_transaction_from_memorypool(self):
        self.Blocksize = 80
        self.TxIds = []
        self.addTransactionsInBlock = []
        self.remove_spent_transactions = []

        for tx_id_hex in self.MemPool:
            tx = self.MemPool[tx_id_hex]
            self.TxIds.append(bytes.fromhex(tx.id()))
            self.addTransactionsInBlock.append(tx)
            self.Blocksize += len(tx.serialize())
            for spent_input in tx.tx_ins:
                self.remove_spent_transactions.append([spent_input.prev_tx, spent_input.prev_index])

    def remove_transactions_from_memorypool(self):
        initial_mempool_size = len(self.MemPool)
        removed_count = 0
        tx_ids_to_remove = [tx.hex() for tx in self.TxIds]

        for tx_id_hex in tx_ids_to_remove:
            if tx_id_hex in self.MemPool:
                del self.MemPool[tx_id_hex]
                removed_count += 1

    def convert_to_json(self):
        self.TxJson = []
        for tx in self.addTransactionsInBlock:
            self.TxJson.append(tx.to_dict())

    def calculate_fee(self):
        self.input_amount = 0
        self.output_amount = 0
        self.fee = 0

        for TxId_index in self.remove_spent_transactions:
            prev_tx_id_hex = TxId_index[0].hex()
            prev_tx_out_index = TxId_index[1]

            if prev_tx_id_hex in self.utxos:
                prev_trans = self.utxos[prev_tx_id_hex]

                if 0 <= prev_tx_out_index < len(prev_trans.tx_outs):
                    input_val = prev_trans.tx_outs[prev_tx_out_index].amount
                    self.input_amount += input_val
                else:
                    print(f"WARNING: Ungültiger Output-Index {prev_tx_out_index} für TxId {prev_tx_id_hex} in UTXOs. Ignoriere diesen Input.")
            else:
                print(f"WARNING: Vorherige Transaktion {prev_tx_id_hex} für Input nicht in UTXOs gefunden. Könnte schon ausgegeben sein oder Fehler.")


        for tx in self.addTransactionsInBlock:
            for i, tx_out in enumerate(tx.tx_outs):
                self.output_amount += tx_out.amount
        self.fee = self.input_amount - self.output_amount

        if self.fee < 0:
            print("WARNING: Gebühr ist negativ! Das bedeutet, dass mehr ausgegeben als eingenommen wurde. Dies deutet auf einen Fehler in der Transaktionsvalidierung oder der Betragsberechnung hin.")
        if self.input_amount == 0 and self.output_amount == 0 and len(self.addTransactionsInBlock) > 1:
            print("WARNING: Input und Output sind Null, obwohl andere Transaktionen als Coinbase im Block sein sollten. Prüfe die read_transaction_from_memorypool und calculate_fee Logik.")

    def addBlock(self, BlockHeight, prevBlockHash):
        self.adjust_target_based_on_price()

        self.read_transaction_from_memorypool()
        self.calculate_fee()

        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()
        self.Blocksize += len(coinbaseTx.serialize())

        initial_coinbase_amount = coinbaseTx.tx_outs[0].amount
        coinbaseTx.tx_outs[0].amount = initial_coinbase_amount + self.fee
        self.TxIds.insert(0, bytes.fromhex(coinbaseTx.id()))
        self.addTransactionsInBlock.insert(0, coinbaseTx)

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()

        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, self.bits)
        blockHeader.mine(self.current_target)

        self.remove_spent_Transactions()
        self.remove_transactions_from_memorypool()
        self.store_uxtos_in_cache()
        self.convert_to_json()

        final_block_size = self.Blocksize

        new_block_obj = Block(
            BlockHeight,
            final_block_size,
            blockHeader,
            len(self.addTransactionsInBlock),
            self.addTransactionsInBlock
        )

        block_dict_for_db = new_block_obj.to_dict()

        self.safeInDB([block_dict_for_db])

    def main(self):
        lastBlock = self.getLastBlock()
        if lastBlock is None:
            self.GenesisBlock()
        else:
            print(f"DEBUG: Letzter Block in DB: Höhe {lastBlock['Height']}, Hash {lastBlock['BlockHeader']['block_hash']}")

        while True:
            lastBlock = self.getLastBlock()
            BlockHeight = lastBlock["Height"] + 1
            prevBlockHash = lastBlock['BlockHeader']["block_hash"]
            self.addBlock(BlockHeight, prevBlockHash)



    def get_current_electricity_price(self):
        filter_id = 4169
        region = "DE"
        resolution = "hour"

        timestamp_url = f"https://www.smard.de/app/chart_data/{filter_id}/{region}/index_{resolution}.json"

        try:
            response = requests.get(timestamp_url, timeout=10)
            response.raise_for_status()
            timestamps_data = response.json()

            if not isinstance(timestamps_data, dict):
                print(
                    f"SMARD API: Unerwartetes Datenformat für Zeitstempel-Antwort (erwarte Dictionary, bekam {type(timestamps_data)}).")
                return None

            timestamps = timestamps_data.get("timestamps", [])

            if not timestamps:
                print("SMARD API: Keine Zeitstempel gefunden oder 'timestamps'-Schlüssel fehlte/war leer.")
                return None

            latest_timestamp_for_file = max(timestamps)

            timeseries_url = f"https://www.smard.de/app/chart_data/{filter_id}/{region}/{filter_id}_{region}_{resolution}_{latest_timestamp_for_file}.json"
            response = requests.get(timeseries_url, timeout=10)
            response.raise_for_status()

            timeseries_data = response.json()

            if not isinstance(timeseries_data, dict):
                print(
                    f"SMARD API: Unerwartetes Datenformat für Zeitreihen-Antwort (erwarte Dictionary, bekam {type(timeseries_data)}).")
                return None

            rows = timeseries_data.get("series", [])

            if not rows:
                print("SMARD API: Keine Zeitreihendaten gefunden oder 'series'-Schlüssel fehlte/war leer.")
                return None

            valid_prices = []
            now = datetime.datetime.now()

            for timestamp_ms, price in rows:
                if price is not None:
                    dt_object = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                    if dt_object <= now:
                        valid_prices.append(price)

            if not valid_prices:
                print(
                    "SMARD API: Keine gültigen (nicht-Null) Strompreise bis zur aktuellen Stunde in der Datei gefunden.")
                return None

            average_price = sum(valid_prices) / len(valid_prices)
            print(
                f"SMARD API: Durchschnittlicher Strompreis der verfügbaren gültigen Stunden: {average_price:.2f} EUR/MWh")
            return average_price

        except requests.exceptions.RequestException as e:
            print(f"SMARD API Fehler bei der Anfrage (Netzwerk/HTTP): {e}")
            return None
        except ValueError as e:
            print(f"SMARD API Fehler beim Parsen der JSON-Antwort (ungültiges JSON): {e}")
            return None
        except Exception as e:
            print(f"SMARD API Ein unerwarteter Fehler ist aufgetreten: {e} (Typ: {type(e).__name__})")
            return None

    def adjust_target_based_on_price(self):

        current_time = time.time()
        if current_time - self.last_price_check_time < self.price_check_interval:
            print("DEBUG: Preisprüfung übersprungen (zu kurzes Intervall seit letzter Prüfung).")
            return

        electricity_price = self.get_current_electricity_price()

        if electricity_price is None:
            print("DEBUG: Konnte keinen Strompreis abrufen. Target bleibt unverändert.")
            return

        if electricity_price <= EEG_EINSPEISE_VERGÜTUNG:
            if electricity_price <= 0 or electricity_price == EEG_EINSPEISE_VERGÜTUNG:
                self.current_target = INITIAL_TARGET
            else:
                price_progress = (electricity_price) / (EEG_EINSPEISE_VERGÜTUNG)
                self.current_target = int(SLIGHTLY_EASIER_TARGET - (SLIGHTLY_EASIER_TARGET - INITIAL_TARGET) * price_progress)
        else:
            price_progress = (EEG_EINSPEISE_VERGÜTUNG/electricity_price)
            self.current_target = int(INITIAL_TARGET * price_progress)


        self.bits = target_to_bits(self.current_target)
        self.last_price_check_time = current_time



if __name__ == "__main__":
    with Manager() as manager:
        utxos = function1(manager)
        MemPool = function2(manager)

        print("Starte Webanwendungsprozess...")
        webapp = Process(target=main, args=(utxos, MemPool))
        webapp.start()
        print("Webanwendungsprozess gestartet.")

        print("Starte Blockchain-Prozess...")
        blockchain = Blockchain(utxos, MemPool)
        blockchain.main()
        print("Blockchain-Prozess gestartet.")