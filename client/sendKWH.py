import time
from Blockchain.backend.util.util import decode_base58
from Blockchain.backend.core.Script import Script
from Blockchain.backend.core.Tx import TxIn, TxOut, Tx  # Ensure Tx is imported
from Blockchain.backend.core.database.database import AccountDB
from Blockchain.backend.core.EllepticCurve.EllepticCurve import PrivateKey


class SendKWH:
    def __init__(self, fromAccount, toAccount, Amount, UTXOS):
        self.COIN = 1000  # Assuming this is your smallest unit, e.g., 1 KWH = 1000 "satoshis"
        self.FromPublicAddress = fromAccount
        self.toAccount = toAccount
        self.Amount = Amount * self.COIN  # Convert human-readable amount to internal units
        self.utxos = UTXOS  # This is the shared multiprocessing.Manager().dict()

        # Define a default fee here, but allow it to be adjusted
        # A fixed fee might be too high or too low. Consider a dynamic fee based on transaction size.
        self.fee = 100  # Example fixed fee in smallest units (e.g., 100 satoshis)

    def scriptPubKey(self, PublicAddress):
        h160 = decode_base58(PublicAddress)
        script_pubkey = Script().p2pkh_script(h160)
        return script_pubkey

    def getPrivateKey(self):
        AllAccounts = AccountDB().read()
        for account in AllAccounts:
            if account['PublicAddress'] == self.FromPublicAddress:
                return account['privateKey']
        return False  # Should probably raise an error if not found

    def prepareTxIn(self):
        TxIns = []
        self.Total = 0  # Total amount from selected inputs

        self.from_address_script_pubkey = self.scriptPubKey(self.FromPublicAddress)
        self.fromPubKeyHash = self.from_address_script_pubkey.cmds[2]

        newutxos = {}

        # --- IMPORTANT: Handle empty UTXOs and avoid busy-waiting ---
        # It's better to make a copy for iteration to avoid issues with Manager.dict()
        try:
            # Attempt to copy the shared dictionary
            # This can still cause issues if utxos is large and frequently updated.
            # But for simple cases, it prevents deadlocks.
            newutxos = dict(self.utxos)
        except Exception as e:
            print(f"Error converting the Managed Dict to Normal Dict: {e}")
            return []  # Return empty list, indicating no inputs could be prepared

        if not newutxos:
            print("DEBUG (sendKWH.py): No UTXOs available in the system.")
            return []  # No UTXOs to select from

        # The amount needed includes the recipient's amount AND the fee
        amount_needed = self.Amount + self.fee
        print(f"DEBUG (sendKWH.py): Benötigter Betrag (inkl. Gebühr): {amount_needed}")

        # Iterate through UTXOs to find suitable inputs
        selected_utxos_count = 0
        for tx_id_hex, tx_obj in newutxos.items():  # tx_id_hex is a string key
            if self.Total >= amount_needed:
                break  # We've collected enough funds

            # Iterate through outputs of this UTXO transaction
            for index, txout in enumerate(tx_obj.tx_outs):
                # Check if this output belongs to the sender
                if txout.script_pubkey.cmds[2] == self.fromPubKeyHash:
                    self.Total += txout.amount
                    prev_tx_bytes = bytes.fromhex(tx_obj.id())  # Get Tx ID as bytes
                    TxIns.append(TxIn(prev_tx_bytes, index))
                    selected_utxos_count += 1
                    print(
                        f"DEBUG (sendKWH.py): Ausgewählter Input: {tx_obj.id()}:{index}, Betrag: {txout.amount}. Aktuelle Input-Summe: {self.Total}")

                    if self.Total >= amount_needed:
                        break  # Got enough, break inner loop too

        print(f"DEBUG (sendKWH.py): Gesamt-Input-Betrag aus UTXOs: {self.Total}")
        print(f"DEBUG (sendKWH.py): Anzahl der ausgewählten Inputs: {selected_utxos_count}")

        self.isBalanceEnough = (self.Total >= amount_needed)  # Check if we gathered enough

        if not self.isBalanceEnough:
            print(f"ERROR (sendKWH.py): Nicht genügend Guthaben. Benötigt: {amount_needed}, Verfügbar: {self.Total}")
            return []  # Indicate failure by returning empty list

        return TxIns

    def prepareTxOut(self):
        TxOuts = []
        to_scriptPubkey = self.scriptPubKey(self.toAccount)
        TxOuts.append(TxOut(self.Amount, to_scriptPubkey))
        print(f"DEBUG (sendKWH.py): Output an Empfänger: {self.Amount}")

        # --- CRITICAL FIX FOR OVERFLOWERROR ---
        self.changeAmount = self.Total - self.Amount - self.fee

        print(f"DEBUG (sendKWH.py): Gesamt Inputs (Total): {self.Total}")
        print(f"DEBUG (sendKWH.py): Betrag an Empfänger (Amount): {self.Amount}")
        print(f"DEBUG (sendKWH.py): Gebühr (Fee): {self.fee}")
        print(f"DEBUG (sendKWH.py): Berechneter Rückgeldbetrag (ChangeAmount): {self.changeAmount}")

        if self.changeAmount < 0:
            # This should ideally be caught by isBalanceEnough in prepareTxIn,
            # but this is a final safeguard.
            print(
                f"CRITICAL ERROR (sendKWH.py): Negative Change Amount ({self.changeAmount}) detected in prepareTxOut!")
            # Raise an error or handle this condition, as it implies insufficient funds.
            raise ValueError("Negative change amount. Transaction cannot be created.")

        # Only add a change output if there's actual change
        if self.changeAmount > 0:
            TxOuts.append(TxOut(self.changeAmount, self.from_address_script_pubkey))
            print(f"DEBUG (sendKWH.py): Rückgeld Output hinzugefügt: {self.changeAmount}")
        else:
            print(f"DEBUG (sendKWH.py): Kein Rückgeld benötigt (changeAmount = 0).")

        return TxOuts

    def signTx(self):
        secret = self.getPrivateKey()
        if not secret:
            print(f"ERROR (sendKWH.py): Privater Schlüssel für {self.FromPublicAddress} nicht gefunden.")
            raise ValueError("Private key not available for signing.")

        priv = PrivateKey(secret=secret)

        for index, tx_in_to_sign in enumerate(self.TxIns):
            # To sign, you need the script_pubkey of the UTXO being spent
            # This is stored in the TxOut of the *previous* transaction

            prev_tx_id_bytes = tx_in_to_sign.prev_tx
            prev_tx_id_hex = prev_tx_id_bytes.hex()
            prev_tx_out_index = tx_in_to_sign.prev_index

            # Retrieve the full previous transaction object from UTXOs
            original_prev_tx_obj = self.utxos.get(prev_tx_id_hex)  # Use .get for safety

            if not original_prev_tx_obj:
                print(
                    f"ERROR (sendKWH.py): Ursprüngliche Transaktion {prev_tx_id_hex} nicht in UTXOs gefunden für Signatur.")
                raise ValueError(f"Missing previous transaction for signing: {prev_tx_id_hex}")

            if not (0 <= prev_tx_out_index < len(original_prev_tx_obj.tx_outs)):
                print(
                    f"ERROR (sendKWH.py): Ungültiger Output-Index {prev_tx_out_index} in voriger Transaktion {prev_tx_id_hex} für Signatur.")
                raise IndexError(f"Invalid previous output index for signing: {prev_tx_out_index}")

            # Get the script_pubkey from the *original* TxOut that this TxIn is spending
            script_pubkey_of_spent_output = original_prev_tx_obj.tx_outs[prev_tx_out_index].script_pubkey

            print(
                f"DEBUG (sendKWH.py): Signiere Input {index} mit script_pubkey: {script_pubkey_of_spent_output.cmds[2].hex()}")

            # The sign_input method in Tx class needs the private key and the script_pubkey of the *spent output*
            self.TxObj.sign_input(index, priv, script_pubkey_of_spent_output)
            print(f"DEBUG (sendKWH.py): Input {index} erfolgreich signiert.")

    def prepareTransaction(self):
        print(
            f"DEBUG (sendKWH.py): Starte prepareTransaction für {self.FromPublicAddress} -> {self.toAccount}, Betrag: {self.Amount / self.COIN}")

        self.TxIns = self.prepareTxIn()
        if not self.isBalanceEnough:  # Check the flag set by prepareTxIn
            print(f"ERROR (sendKWH.py): Unzureichendes Guthaben oder Fehler bei Input-Vorbereitung.")
            return False  # Indicate failure

        self.TxOuts = self.prepareTxOut()

        # Create the transaction object AFTER inputs and outputs are prepared
        self.TxObj = Tx(1, self.TxIns, self.TxOuts, 0)  # version=1, locktime=0 (adjust if needed)

        # Calculate TxId AFTER TxObj is fully formed (inputs and outputs are set)
        # This will compute the hash based on the current state of TxObj
        self.TxObj.TxId = self.TxObj.id()
        print(f"DEBUG (sendKWH.py): Transaktionsobjekt erstellt. Temp TxId: {self.TxObj.TxId}")

        self.signTx()

        # After signing, recalculate TxId if signature changes the hash
        # If your Tx.id() depends on script_sig (which it should), then recalculate.
        # If Tx.id() is calculated based on parts that don't include script_sig for hashing,
        # then the initial TxId set before signing might be sufficient.
        # Assuming Tx.id() needs to be called after signatures are in TxIns:
        self.TxObj.TxId = self.TxObj.id()
        print(f"DEBUG (sendKWH.py): Finale TxId nach Signatur: {self.TxObj.TxId}")

        return self.TxObj