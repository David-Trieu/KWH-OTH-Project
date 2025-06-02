from Blockchain.backend.util.util import decode_base58
class SendKWH:
    def __init__(self, fromAccount, toAccount, Amount, UTXOS):
        self.COIN = 1000
        self.fromPublicAddress = fromAccount
        self.toAccount = toAccount
        self.Amount = Amount
        self.UTXOS = UTXOS



    def prepareTxIn(self):
        TxIns = []
        self.Total = 0

    def prepareTxOut(self):
        pass

    def prepareTransaction(self):
        self.prepareTxIn()
        self.prepareTxOut()