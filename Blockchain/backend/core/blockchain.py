import sys
import time
import requests
import datetime
from multiprocessing import Process, Manager

# Passe diesen Pfad an DEINE Umgebung an!
sys.path.append('/Users/David/Desktop/KWH-OTH-Project')

from Blockchain.backend.core.block import Block
from Blockchain.backend.core.blockheader import BlockHeader
from Blockchain.backend.util.util import hash256, merkle_root, target_to_bits
from Blockchain.backend.core.database.database import BlockchainDB
from Blockchain.backend.core.Tx import CoinbaseTx
from Blockchain.frontend.run import main # Annahme: 'main' aus frontend/run ist die Webapp

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
        print(f"\n--- DEBUG: Erstelle Genesis Block (Höhe: {BlockHeight}) ---")
        self.addBlock(BlockHeight, prevBlockHash)
        print(f"--- DEBUG: Genesis Block erstellt ---")

    # Keep Track of all unspent Transactions in cache memory for fast retrival
    def store_uxtos_in_cache(self):
        print(f"\n--- DEBUG: starte store_uxtos_in_cache ---")
        for tx in self.addTransactionsInBlock:
            tx_id_hex = tx.id()
            print(f"DEBUG: Füge neue UTXO hinzu: TxId {tx_id_hex} mit {len(tx.tx_outs)} Outputs.")
            self.utxos[tx_id_hex] = tx
            # Zusätzlicher Debug: Prüfe die Outputs der hinzugefügten Transaktion
            for i, tx_out in enumerate(tx.tx_outs):
                print(f"DEBUG: Inspecting TxOut object type: {type(tx_out)}")
                print(f"DEBUG: TxOut object attributes: {dir(tx_out)}")  # This will list all attributes
                # ... then try the fix based on what you see in dir(tx_out)
        print(f"--- DEBUG: store_uxtos_in_cache beendet. Aktuelle UTXOs im Cache: {len(self.utxos)} ---")

    def remove_spent_Transactions(self):
        print(f"\n--- DEBUG: starte remove_spent_Transactions ---")
        # Initialize an empty list to track which UTXOs to remove completely
        utxos_to_delete_from_cache = []

        print(f"DEBUG: Anzahl der zu entfernenden/aktualisierenden Spents: {len(self.remove_spent_transactions)}")

        # Create a copy for iteration to avoid issues if remove_spent_transactions is modified
        # (though in this loop it shouldn't be, it's good practice)
        spent_transactions_to_process = list(self.remove_spent_transactions)

        # It's important to clear remove_spent_transactions here, as it's populated for the *current* block.
        # If the block isn't mined, it might be processed again.
        # For simplicity, if we assume a block is always eventually mined or rejected, clearing it here is okay.
        # However, for robustness, you might want to clear it *after* a successful block commit.
        # For now, let's keep it as is, as the issue is UTXO update, not list clearing.

        for txId_index in spent_transactions_to_process:
            prev_tx_id_bytes = txId_index[0]
            prev_tx_id_hex = prev_tx_id_bytes.hex()
            prev_tx_out_index = txId_index[1]

            print(f"DEBUG: Bearbeite spent: PrevTxId={prev_tx_id_hex}, PrevIndex={prev_tx_out_index}")

            if prev_tx_id_hex in self.utxos:
                # Retrieve the object from Manager.dict()
                prev_trans_utxo = self.utxos[prev_tx_id_hex]

                print(
                    f"DEBUG: Gefunden in UTXOs: TxId {prev_tx_id_hex}. Outputs vor dem Entfernen: {len(prev_trans_utxo.tx_outs)}")

                if 0 <= prev_tx_out_index < len(prev_trans_utxo.tx_outs):
                    spent_output_amount = prev_trans_utxo.tx_outs[prev_tx_out_index].amount
                    print(f"DEBUG: Output {prev_tx_out_index} (Amount: {spent_output_amount}) wird als spent markiert.")

                    # Create a new list of TxOuts excluding the spent one
                    new_tx_outs = [
                        tx_out for i, tx_out in enumerate(prev_trans_utxo.tx_outs)
                        if i != prev_tx_out_index
                    ]

                    if not new_tx_outs:
                        # If no outputs remain, mark the entire transaction for deletion from UTXOs
                        print(
                            f"DEBUG: Markiere Transaktion {prev_tx_id_hex} zur vollständigen Entfernung (alle Outputs verbraucht).")
                        utxos_to_delete_from_cache.append(prev_tx_id_hex)
                    else:
                        # Update the tx_outs attribute of the Tx object
                        prev_trans_utxo.tx_outs = new_tx_outs
                        # Explicitly re-assign the modified object back to the Manager.dict()
                        self.utxos[prev_tx_id_hex] = prev_trans_utxo
                        print(
                            f"DEBUG: TxId {prev_tx_id_hex} hat noch {len(new_tx_outs)} unverbrauchte Outputs. UTXO-Cache aktualisiert.")
                else:
                    print(
                        f"WARNING: PrevIndex {prev_tx_out_index} ist für TxId {prev_tx_id_hex} ungültig (bereits ausgegeben?). Überspringe.")
            else:
                print(
                    f"WARNING: Vorherige Transaktion {prev_tx_id_hex} für Input nicht in UTXOs gefunden. Könnte schon ausgegeben sein oder Fehler.")

        # Finally, remove all transactions marked for complete deletion
        for tx_id_hex in utxos_to_delete_from_cache:
            if tx_id_hex in self.utxos:  # Check again in case it was already removed by another input in the same block
                print(f"DEBUG: Entferne Transaktion {tx_id_hex} vollständig aus UTXOs (keine Outputs mehr).")
                del self.utxos[tx_id_hex]

        print(f"--- DEBUG: remove_spent_Transactions beendet. Aktuelle UTXOs im Cache: {len(self.utxos)} ---")

    def read_transaction_from_memorypool(self):
        self.Blocksize = 80 # Block Header size (approx)
        self.TxIds = []
        self.addTransactionsInBlock = []
        self.remove_spent_transactions = [] # Liste von [prev_tx_id_bytes, prev_tx_out_index]

        print(f"\n--- DEBUG: starte read_transaction_from_memorypool ---")
        print(f"DEBUG: MemPool enthält {len(self.MemPool)} Transaktionen.")

        for tx_id_hex in self.MemPool:
            tx = self.MemPool[tx_id_hex]
            self.TxIds.append(bytes.fromhex(tx.id())) # TxId als Bytes für Merkle Root
            self.addTransactionsInBlock.append(tx)
            self.Blocksize += len(tx.serialize())  # add transactions size to blocksize

            print(f"DEBUG: Transaktion aus MemPool hinzugefügt: {tx_id_hex}")
            print(f"DEBUG:   Anzahl Inputs: {len(tx.tx_ins)}, Anzahl Outputs: {len(tx.tx_outs)}")

            for spent_input in tx.tx_ins:
                # Hier sammeln wir die Inputs, die als 'spent' markiert werden müssen
                self.remove_spent_transactions.append([spent_input.prev_tx, spent_input.prev_index])
                print(f"DEBUG:   Markiere Input als spent: PrevTxId={spent_input.prev_tx.hex()}, PrevIndex={spent_input.prev_index}")

        print(f"--- DEBUG: read_transaction_from_memorypool beendet. {len(self.addTransactionsInBlock)} Transaktionen für den Block gesammelt. ---")

    def remove_transactions_from_memorypool(self):
        print(f"\n--- DEBUG: starte remove_transactions_from_memorypool ---")
        initial_mempool_size = len(self.MemPool)
        removed_count = 0
        tx_ids_to_remove = [tx.hex() for tx in self.TxIds] # Sicherstellen, dass TxIds im richtigen Format sind

        for tx_id_hex in tx_ids_to_remove:
            if tx_id_hex in self.MemPool:
                del self.MemPool[tx_id_hex]
                removed_count += 1
                print(f"DEBUG: Transaktion aus MemPool entfernt: {tx_id_hex}")
        print(f"--- DEBUG: remove_transactions_from_memorypool beendet. {removed_count} von {initial_mempool_size} Transaktionen entfernt. ---")


    def convert_to_json(self):
        self.TxJson = []
        print(f"\n--- DEBUG: starte convert_to_json ---")
        for tx in self.addTransactionsInBlock:
            self.TxJson.append(tx.to_dict())
            # print(f"DEBUG: Transaktion {tx.TxId.hex()} zu JSON konvertiert.") # Zu viele Prints
        print(f"--- DEBUG: convert_to_json beendet. {len(self.TxJson)} Transaktionen konvertiert. ---")


    def calculate_fee(self):
        self.input_amount = 0
        self.output_amount = 0
        self.fee = 0 # Initialisiere Fee

        print(f"\n--- DEBUG: starte calculate_fee ---")
        print(f"DEBUG: Anzahl der Inputs, die geprüft werden (aus remove_spent_transactions): {len(self.remove_spent_transactions)}")

        """ Calculate Input Amount """
        for TxId_index in self.remove_spent_transactions:
            prev_tx_id_hex = TxId_index[0].hex()
            prev_tx_out_index = TxId_index[1]

            if prev_tx_id_hex in self.utxos:
                # Hole die gesamte vorherige Transaktion aus den UTXOs
                prev_trans = self.utxos[prev_tx_id_hex]

                if 0 <= prev_tx_out_index < len(prev_trans.tx_outs):
                    input_val = prev_trans.tx_outs[prev_tx_out_index].amount
                    self.input_amount += input_val
                    print(f"DEBUG: Input-Betrag hinzugefügt: {input_val} von {prev_tx_id_hex}:{prev_tx_out_index}. Gesamter Input: {self.input_amount}")
                else:
                    print(f"WARNING: Ungültiger Output-Index {prev_tx_out_index} für TxId {prev_tx_id_hex} in UTXOs. Ignoriere diesen Input.")
            else:
                print(f"WARNING: Vorherige Transaktion {prev_tx_id_hex} für Input nicht in UTXOs gefunden. Könnte schon ausgegeben sein oder Fehler.")
                # Wenn ein Input nicht in UTXOs gefunden wird, ist das ein Problem.
                # Es bedeutet, dass eine Transaktion im MemPool einen bereits ausgegebenen Input verwendet hat.
                # In einer echten Blockchain würde diese Transaktion als ungültig abgelehnt.
                # Für Debugging: Prüfe, ob dies der Grund ist, warum deine Gebühren falsch sind.


        """ Calculate Output Amount """
        for tx in self.addTransactionsInBlock:
            for i, tx_out in enumerate(tx.tx_outs):
                self.output_amount += tx_out.amount
                print(f"DEBUG: Output-Betrag hinzugefügt: {tx_out.amount} von Tx {tx.id()}, Output {i}. Gesamter Output: {self.output_amount}")

        self.fee = self.input_amount - self.output_amount
        print(f"--- DEBUG: calculate_fee beendet ---")
        print(f"DEBUG: Gesamt Input-Betrag: {self.input_amount}")
        print(f"DEBUG: Gesamt Output-Betrag: {self.output_amount}")
        print(f"DEBUG: Berechnete Fee: {self.fee}")

        if self.fee < 0:
            print("WARNING: Gebühr ist negativ! Das bedeutet, dass mehr ausgegeben als eingenommen wurde. Dies deutet auf einen Fehler in der Transaktionsvalidierung oder der Betragsberechnung hin.")
        if self.input_amount == 0 and self.output_amount == 0 and len(self.addTransactionsInBlock) > 1:
            # Wenn es andere Transaktionen als Coinbase gibt, aber 0 Input/Output, stimmt was nicht
            print("WARNING: Input und Output sind Null, obwohl andere Transaktionen als Coinbase im Block sein sollten. Prüfe die read_transaction_from_memorypool und calculate_fee Logik.")


    def addBlock(self, BlockHeight, prevBlockHash):
        print(f"\n===== DEBUG: Starte addBlock (Höhe: {BlockHeight}) =====")
        print(f"DEBUG: Aktueller Target vor Anpassung: {hex(self.current_target)}")
        self.adjust_target_based_on_price()
        print(f"DEBUG: Aktueller Target nach Anpassung: {hex(self.current_target)}, Bits: {self.bits}")

        self.read_transaction_from_memorypool()
        self.calculate_fee() # Ruft die Gebührenberechnung auf

        timestamp = int(time.time())
        coinbaseInstance = CoinbaseTx(BlockHeight)
        coinbaseTx = coinbaseInstance.CoinbaseTransaction()
        print(f"DEBUG: Ursprüngliche Coinbase Belohnung (ohne Gebühren): {coinbaseTx.tx_outs[0].amount}")
        self.Blocksize += len(coinbaseTx.serialize())  # add coinbasetx size to blocksize

        # Hier wird die Gebühr zur Coinbase-Transaktion hinzugefügt
        initial_coinbase_amount = coinbaseTx.tx_outs[0].amount
        coinbaseTx.tx_outs[0].amount = initial_coinbase_amount + self.fee
        print(f"DEBUG: Coinbase Belohnung nach Gebühren-Addierung: {coinbaseTx.tx_outs[0].amount} (Ursprünglich: {initial_coinbase_amount}, Fee: {self.fee})")


        self.TxIds.insert(0, bytes.fromhex(coinbaseTx.id())) # Füge Coinbase TxId an erster Stelle hinzu
        self.addTransactionsInBlock.insert(0, coinbaseTx) # Füge Coinbase Tx an erster Stelle der Block-Transaktionen hinzu

        merkleRoot = merkle_root(self.TxIds)[::-1].hex()
        print(f"DEBUG: Merkle Root: {merkleRoot}")

        blockHeader = BlockHeader(VERSION, prevBlockHash, merkleRoot, timestamp, self.bits)
        print(f"DEBUG: Starte Mining für Block {BlockHeight}...")
        blockHeader.mine(self.current_target)
        print(f"DEBUG: Mining beendet. Nonce: {blockHeader.nonce}, Block Hash: {blockHeader.blockHash}")

        self.remove_spent_Transactions() # Hier werden die verbrauchten UTXOs entfernt/aktualisiert
        self.remove_transactions_from_memorypool() # Hier werden die Transaktionen aus dem Mempool entfernt
        self.store_uxtos_in_cache() # Hier werden die neuen UTXOs (inkl. Rückgeld) hinzugefügt
        self.convert_to_json()

        print(f"Block Height {BlockHeight} mined successfully with Nonce value of {blockHeader.nonce}")

        # Sicherstellen, dass Blocksize korrekt übergeben wird
        final_block_size = self.Blocksize
        print(f"DEBUG: Final Blocksize: {final_block_size}")

        self.safeInDB([Block(BlockHeight, final_block_size, blockHeader.__dict__, 1,
                             self.TxJson).__dict__])  # added actual BLocksize to block
        print(f"===== DEBUG: addBlock (Höhe: {BlockHeight}) beendet =====")


    def main(self):
        print("\n--- DEBUG: Starte Blockchain Main Loop ---")
        lastBlock = self.getLastBlock()
        if lastBlock is None:
            print("DEBUG: Kein letzter Block gefunden. Erstelle Genesis Block.")
            self.GenesisBlock()
        else:
            print(f"DEBUG: Letzter Block in DB: Höhe {lastBlock['Height']}, Hash {lastBlock['BlockHeader']['blockHash']}")

        while True:
            lastBlock = self.getLastBlock()
            BlockHeight = lastBlock["Height"] + 1
            print(f"\n--- DEBUG: Beginne mit Mining von Block {BlockHeight} ---")
            prevBlockHash = lastBlock['BlockHeader']["blockHash"]
            self.addBlock(BlockHeight, prevBlockHash)
            # Eine kleine Pause, um die Ausgaben lesbar zu halten und nicht zu spammen
            # time.sleep(1)


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
            print(
                f"SMARD API: Neuester Zeitstempel für Datei: {latest_timestamp_for_file} ({datetime.datetime.fromtimestamp(latest_timestamp_for_file / 1000)})")

            timeseries_url = f"https://www.smard.de/app/chart_data/{filter_id}/{region}/{filter_id}_{region}_{resolution}_{latest_timestamp_for_file}.json"
            print(f"SMARD API: Anfrage an Zeitreihen-URL: {timeseries_url}")
            response = requests.get(timeseries_url, timeout=10)
            response.raise_for_status()

            print(f"SMARD API: Zeitreihen-Antwort Status Code: {response.status_code}")
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
            print("DEBUG: Preisprüfung übersprungen (zu kurzes Intervall seit letzter Prüfung).")
            return

        electricity_price = self.get_current_electricity_price()

        if electricity_price is None:
            print("DEBUG: Konnte keinen Strompreis abrufen. Target bleibt unverändert.")
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
            if (P2 - P1) == 0:
                self.current_target = T2
            else:
                price_progress = (clamped_price - P1) / (P2 - P1)
                self.current_target = int(T1 - (T1 - T2) * price_progress)
        else:
            if (P3 - P2) == 0:
                self.current_target = T2
            else:
                price_progress = (clamped_price - P2) / (P3 - P2)
                self.current_target = int(T2 - (T2 - T3) * price_progress)

        # Sicherstellen, dass das End-Target immer innerhalb der absoluten Grenzen bleibt
        self.current_target = max(MIN_ADJUSTED_TARGET, min(SLIGHTLY_EASIER_TARGET, self.current_target))

        self.bits = target_to_bits(self.current_target)
        print(f"DEBUG: Target angepasst: Durchschnittlicher Preis {electricity_price:.2f} EUR/MWh -> Neues Target (hex): {hex(self.current_target)}, Bits: {self.bits}")
        self.last_price_check_time = current_time


if __name__ == "__main__":
    with Manager() as manager:
        utxos = manager.dict()
        MemPool = manager.dict()

        print("Starte Webanwendungsprozess...")
        webapp = Process(target=main, args=(utxos, MemPool))
        webapp.start()
        print("Webanwendungsprozess gestartet.")

        print("Starte Blockchain-Prozess...")
        blockchain = Blockchain(utxos, MemPool)
        blockchain.main()
        print("Blockchain-Prozess gestartet.")