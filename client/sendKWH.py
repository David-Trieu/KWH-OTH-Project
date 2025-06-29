import time
from Blockchain.backend.util.util import decode_base58
from Blockchain.backend.core.Script import Script
from Blockchain.backend.core.Tx import TxIn, TxOut, Tx
from Blockchain.backend.core.database.database import AccountDB
from Blockchain.backend.core.EllepticCurve.EllepticCurve import PrivateKey
#from Blockchain.backend.core.blockchain import Blockchain


class SendKWH:
    def __init__(self, fromAccount, toAccount, Amount, UTXOS):
        self.COIN = 1000
        self.FromPublicAddress = fromAccount
        self.toAccount = toAccount
        self.Amount = Amount * self.COIN
        self.utxos = UTXOS

        self.fee = 100

    def scriptPubKey(self, PublicAddress):
        h160 = decode_base58(PublicAddress)
        script_pubkey = Script().p2pkh_script(h160)
        return script_pubkey

    def getPrivateKey(self):
        AllAccounts = AccountDB().read()
        for account in AllAccounts:
            if account['PublicAddress'] == self.FromPublicAddress:
                return account['privateKey']
        return False

    def prepareTxIn(self):
        TxIns = []
        self.Total = 0

        self.from_address_script_pubkey = self.scriptPubKey(self.FromPublicAddress)
        self.fromPubKeyHash = self.from_address_script_pubkey.cmds[2]

        newutxos = {}

        try:
            newutxos = dict(self.utxos)
        except Exception as e:
            print(f"Error converting the Managed Dict to Normal Dict: {e}")
            return []

        if not newutxos:
            print("DEBUG (sendKWH.py): No UTXOs available in the system.")
            return []

        amount_needed = self.Amount + self.fee

        selected_utxos_count = 0
        for tx_id_hex, tx_obj in newutxos.items():
            if self.Total >= amount_needed:
                break

            for index, txout in enumerate(tx_obj.tx_outs):
                if txout.script_pubkey.cmds[2] == self.fromPubKeyHash:
                    self.Total += txout.amount
                    prev_tx_bytes = bytes.fromhex(tx_obj.id())
                    TxIns.append(TxIn(prev_tx_bytes, index))
                    selected_utxos_count += 1
                    print(
                        f"DEBUG (sendKWH.py): Ausgewählter Input: {tx_obj.id()}:{index}, Betrag: {txout.amount}. Aktuelle Input-Summe: {self.Total}")

                    if self.Total >= amount_needed:
                        break

        self.isBalanceEnough = (self.Total >= amount_needed)

        if not self.isBalanceEnough:
            print(f"ERROR (sendKWH.py): Nicht genügend Guthaben. Benötigt: {amount_needed}, Verfügbar: {self.Total}")
            return []

        return TxIns

    def prepareTxOut(self):
        TxOuts = []
        to_scriptPubkey = self.scriptPubKey(self.toAccount)
        TxOuts.append(TxOut(self.Amount, to_scriptPubkey))

        self.changeAmount = self.Total - self.Amount - self.fee


        if self.changeAmount < 0:
            raise ValueError("Negative change amount. Transaction cannot be created.")

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
            prev_tx_id_bytes = tx_in_to_sign.prev_tx
            prev_tx_id_hex = prev_tx_id_bytes.hex()
            prev_tx_out_index = tx_in_to_sign.prev_index

            original_prev_tx_obj = self.utxos.get(prev_tx_id_hex)

            if not original_prev_tx_obj:
                raise ValueError(f"Missing previous transaction for signing: {prev_tx_id_hex}")

            if not (0 <= prev_tx_out_index < len(original_prev_tx_obj.tx_outs)):
                raise IndexError(f"Invalid previous output index for signing: {prev_tx_out_index}")

            script_pubkey_of_spent_output = original_prev_tx_obj.tx_outs[prev_tx_out_index].script_pubkey
            self.TxObj.sign_input(index, priv, script_pubkey_of_spent_output)

    def prepareTransaction(self):
        self.TxIns = self.prepareTxIn()
        if not self.isBalanceEnough:
            return False

        self.TxOuts = self.prepareTxOut()

        self.TxObj = Tx(1, self.TxIns, self.TxOuts, 0)

        self.TxObj.TxId = self.TxObj.id()

        self.signTx()

        self.TxObj.TxId = self.TxObj.id()
        return self.TxObj