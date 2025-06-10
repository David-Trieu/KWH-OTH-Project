from flask import Flask, render_template, request

from client.sendKWH import SendKWH
from Blockchain.backend.core.Tx import Tx

app = Flask(__name__)

@app.route('/', methods = ['GET', 'POST'])
def index():

    message = ""
    return render_template('index.html', message = message)

@app.route('/wallet', methods = ['GET', 'POST'])
def wallet():
    message = ''
    if request.method == 'POST':
        print("test")
        FromAddress = request.form.get('fromAddress')
        ToAddress = request.form.get('toAddress')
        Amount = request.form.get('Amount', type = int)
        sendCoin = SendKWH(FromAddress, ToAddress, Amount, UTXOS)
        TxObj = sendCoin.prepareTransaction()

        scriptPubKey = sendCoin.scriptPubKey(FromAddress)
        verified = True

        if not TxObj:
            message= "Invalid Transaction"

        if isinstance(TxObj, Tx):
            for index, tx in enumerate(TxObj.tx_ins):
                if not TxObj.verify_input(index, scriptPubKey):
                    verified = False

            if verified:
                MEMPOOL[TxObj.TxId] = TxObj
                message = "Transaction added in MemoryPool"

    return render_template('wallet.html', message = message)


def main(utxos, MemPool):
    global UTXOS
    global MEMPOOL
    UTXOS = utxos
    MEMPOOL = MemPool
    app.run()
