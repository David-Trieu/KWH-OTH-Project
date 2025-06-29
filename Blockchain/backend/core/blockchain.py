import sys

sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256, merkle_root, target_to_bits
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx
from multiprocessing import Process, Manager
from Blockchain.frontend.run import main

import time
import requests
import datetime

ZERO_HASH = '0' * 64
VERSION = 1
INITIAL_TARGET = 0x00000FFFF0000000000000000000000000000000000000000000000000000000
PRICE_MAX = 300  # Oberer Grenzwert für den Strompreis zur Anpassung
PRICE_MIN = 0  # Unterer Grenzwert für den Strompreis zur Anpassung (Preis kann auch negativ sein, 0 als Safe-Guard)

EEG_UMLAGE_PRICE = 12.60  # Der "neutrale" Strompreispunkt, bei dem das Target INITIAL_TARGET ist

MIN_TARGET_REDUCTION_FACTOR = 0.5  # Definiert, wie viel schwerer das Mining maximal werden kann
MIN_ADJUSTED_TARGET = int(INITIAL_TARGET * MIN_TARGET_REDUCTION_FACTOR)

SMALL_EASIER_FACTOR = 0.05  # Z.B. 0.05 bedeutet Target wird maximal 5% höher als INITIAL_TARGET
SLIGHTLY_EASIER_TARGET = int(INITIAL_TARGET * (1 + SMALL_EASIER_FACTOR))




class Blockchain:
    def __init__(self, utxos, MemPool):
        self.utxos = utxos
        self.MemPool = MemPool
        self.current_target = INITIAL_TARGET
        self.bits = target_to_bits(INITIAL_TARGET)
        self.last_price_check_time = 0
        self.price_check_interval = 3600

    def safeInDB(self, block):
        db = BlockchainDB()
        db.write(block)

    def getLastBlock(self):
        db = BlockchainDB()
        return db.lastBlock()

    def GenesisBlock(self):
        BlockHeight = 0
        prevBlockHash = ZERO_HASH
        self.addBlock(BlockHeight, prevBlockHash)

    # Keep Track of all unspent Transactions in cache memory for fast retrival
    def store_uxtos_in_cache(self):
        for tx in self.addTransactionsInBlock:
            print(f"Transaction added {tx.TxId}")
            self.utxos[tx.TxId] = tx

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
        self.Blocksize = 80
        self.TxIds = []
        self.addTransactionsInBlock = []
        self.remove_spent_transactions = []

        for tx in self.MemPool:
            self.TxIds.append(bytes.fromhex(tx))
            self.addTransactionsInBlock.append(self.MemPool[tx])
            self.Blocksize += len(self.MemPool[tx].serialize())  # add transactions size to blocksize

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

    def calculate_fee(self):
        self.input_amount = 0
        self.output_amount = 0

        # calc input amount
        for TxId_index in self.remove_spent_transactions:
            if TxId_index[0].hex() in self.utxos:
                self.input_amount += self.utxos[TxId_index[0].hex()].tx_outs[TxId_index[1]].amount

        # calc output
        for tx in self.addTransactionsInBlock:
            for tx_out in tx.tx_outs:
                self.output_amount += tx_out.amount

        self.fee = self.input_amount - self.output_amount

    def addBlock(self, BlockHeight, prevBlockHash):

        self.adjust_target_based_on_price()

        self.read_transaction_from_memorypool()
        self.calculate_fee()
        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()
        self.Blocksize += len(coinbaseTx.serialize())  # add coinbasetx size to blocksize

        coinbaseTx.tx_outs[0].amount = coinbaseTx.tx_outs[0].amount + self.fee

        self.TxIds.insert(0, bytes.fromhex(coinbaseTx.id()))
        self.addTransactionsInBlock.insert(0, coinbaseTx)

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()
        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, self.bits)
        blockHeader.mine(self.current_target)

        self.remove_spent_Transactions()
        self.remove_transactions_from_memorypool()
        self.store_uxtos_in_cache()
        self.convert_to_json()

        print(f"Block Height {BlockHeight} mined successfully with Nonce value of {blockHeader.nonce}")
        self.safeInDB([Block(BlockHeight, self.Blocksize, blockHeader.__dict__, 1,
                             self.TxJson).__dict__])  # added actual BLocksize to block

    def main(self):
        lastBlock = self.getLastBlock()
        if lastBlock is None:
            self.GenesisBlock()
        while True:
            lastBlock = self.getLastBlock()
            BlockHeight = lastBlock["Height"] + 1
            prevBlockHash = lastBlock['BlockHeader']["blockHash"]
            self.addBlock(BlockHeight, prevBlockHash)

    def get_current_electricity_price(self):
        filter_id = 4169
        region = "DE"
        resolution = "hour"

        timestamp_url = f"https://www.smard.de/app/chart_data/{filter_id}/{region}/index_{resolution}.json"

        try:
            print(f"SMARD API: Anfrage an Zeitstempel-URL: {timestamp_url}")
            response = requests.get(timestamp_url, timeout=10)
            response.raise_for_status()

            print(f"SMARD API: Zeitstempel-Antwort Status Code: {response.status_code}")
            # print(f"SMARD API: Zeitstempel-Antwort Text (Anfang): {response.text[:500]}...")

            timestamps_data = response.json()

            if not isinstance(timestamps_data, dict):
                print(
                    f"SMARD API: Unerwartetes Datenformat für Zeitstempel-Antwort (erwarte Dictionary, bekam {type(timestamps_data)}).")
                # print(f"SMARD API: Zeitstempel-Antwortinhalt: {timestamps_data}")
                return None

            timestamps = timestamps_data.get("timestamps", [])

            if not timestamps:
                print("SMARD API: Keine Zeitstempel gefunden oder 'timestamps'-Schlüssel fehlte/war leer.")
                return None

            latest_timestamp_for_file = max(timestamps)
            print(
                f"SMARD API: Neuester Zeitstempel für Datei: {latest_timestamp_for_file} ({datetime.datetime.fromtimestamp(latest_timestamp_for_file / 1000)})")

            timeseries_url = f"https://www.smard.de/app/chart_data/{filter_id}/{region}/{filter_id}_{region}_{resolution}_{latest_timestamp_for_file}.json"
            print(f"SMARD API: Anfrage an Zeitreihen-URL: {timeseries_url}")
            response = requests.get(timeseries_url, timeout=10)
            response.raise_for_status()

            print(f"SMARD API: Zeitreihen-Antwort Status Code: {response.status_code}")
            # print(f"SMARD API: Zeitreihen-Antwort Text (Anfang): {response.text[:500]}...") # Zu viel Ausgabe im Normalfall

            timeseries_data = response.json()

            if not isinstance(timeseries_data, dict):
                print(
                    f"SMARD API: Unerwartetes Datenformat für Zeitreihen-Antwort (erwarte Dictionary, bekam {type(timeseries_data)}).")
                # print(f"SMARD API: Zeitreihen-Antwortinhalt: {timeseries_data}") # Zu viel Ausgabe im Normalfall
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
                    if dt_object <= now:  # Nur Daten bis zur aktuellen Stunde berücksichtigen
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
        """
        Passt das Mining-Target basierend auf dem aktuellen Strompreis an.
        Neue Logik:
        - Bei EEG_UMLAGE_PRICE (12.60) -> INITIAL_TARGET (Neutral)
        - Steigt der Preis über EEG_UMLAGE_PRICE -> Target sinkt (Mining wird schwerer)
        - Fällt der Preis unter EEG_UMLAGE_PRICE -> Target steigt minimal (Mining wird minimal leichter)
        """
        current_time = time.time()
        if current_time - self.last_price_check_time < self.price_check_interval:
            print("Preisprüfung übersprungen (zu kurzes Intervall seit letzter Prüfung).")
            return

        electricity_price = self.get_current_electricity_price()

        if electricity_price is None:
            print("Konnte keinen Strompreis abrufen. Target bleibt unverändert.")
            return

        # Den Preis auf den definierten Gesamtbereich begrenzen
        clamped_price = max(PRICE_MIN, min(PRICE_MAX, electricity_price))

        # Definition der drei Referenzpunkte für die Preis-Target-Zuordnung
        P1 = PRICE_MIN  # Unterer Preisgrenzwert (z.B. 0)
        P2 = EEG_UMLAGE_PRICE  # Neutraler Preiswert (12.60)
        P3 = PRICE_MAX  # Oberer Preisgrenzwert (z.B. 300)

        T1 = SLIGHTLY_EASIER_TARGET  # Target bei P1 (absolut leichtestes Mining)
        T2 = INITIAL_TARGET  # Target bei P2 (neutrales Mining)
        T3 = MIN_ADJUSTED_TARGET  # Target bei P3 (absolut schwerstes Mining)

        if clamped_price <= EEG_UMLAGE_PRICE:
            # Segment 1: Preis liegt zwischen PRICE_MIN und EEG_UMLAGE_PRICE (inklusive)
            # Ziel: Target soll von T1 (sehr leicht) zu T2 (neutral) sinken.
            # D.h. je höher der Preis (im Bereich 0-12.60), desto schwerer wird Mining (Target sinkt).
            if (P2 - P1) == 0:  # Division durch Null vermeiden, falls P1 = P2
                self.current_target = T2  # Bei gleichem Preis und neutralem Punkt, neutrales Target
            else:
                # price_progress geht von 0 (bei P1) zu 1 (bei P2)
                price_progress = (clamped_price - P1) / (P2 - P1)
                # Target interpolieren: T1 ist Startpunkt, (T1-T2) ist die Spanne, die abgezogen wird
                self.current_target = int(T1 - (T1 - T2) * price_progress)
        else:  # clamped_price > EEG_UMLAGE_PRICE
            # Segment 2: Preis liegt zwischen EEG_UMLAGE_PRICE und PRICE_MAX
            # Ziel: Target soll von T2 (neutral) zu T3 (sehr schwer) sinken.
            # D.h. je höher der Preis (im Bereich 12.60-300), desto schwerer wird Mining (Target sinkt).
            if (P3 - P2) == 0:  # Division durch Null vermeiden, falls P2 = P3
                self.current_target = T2  # Bei gleichem Preis und neutralem Punkt, neutrales Target
            else:
                # price_progress geht von 0 (bei P2) zu 1 (bei P3)
                price_progress = (clamped_price - P2) / (P3 - P2)
                # Target interpolieren: T2 ist Startpunkt, (T2-T3) ist die Spanne, die abgezogen wird
                self.current_target = int(T2 - (T2 - T3) * price_progress)

        # Sicherstellen, dass das End-Target immer innerhalb der absoluten Grenzen bleibt
        # Der gesamte Bereich der möglichen Targets ist von MIN_ADJUSTED_TARGET bis SLIGHTLY_EASIER_TARGET
        self.current_target = max(MIN_ADJUSTED_TARGET, min(SLIGHTLY_EASIER_TARGET, self.current_target))

        self.bits = target_to_bits(self.current_target)
        print(f"Aktuelles Target: {hex(self.current_target)}")
        print(
            f"Target angepasst: Durchschnittlicher Preis {electricity_price:.2f} EUR/MWh -> Neues Target (hex): {hex(self.current_target)}, Bits: {self.bits}")
        self.last_price_check_time = current_time


if __name__ == "__main__":
    with Manager() as manager:
        utxos = manager.dict()
        MemPool = manager.dict()

        webapp = Process(target=main, args=(utxos, MemPool))
        webapp.start()

        blockchain = Blockchain(utxos, MemPool)
        blockchain.main()