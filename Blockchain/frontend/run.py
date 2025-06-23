from flask import Flask, render_template, request, session, redirect, url_for

from client.accountInfo import accountInfo
from client.sendKWH import SendKWH
from Blockchain.backend.core.Tx import Tx

app = Flask(__name__)

app.secret_key = 'BAD_SECRET_KEY'

@app.route('/', methods = ['GET', 'POST'])
def index():

    message = ""
    return render_template('index.html', message = message)

@app.route('/login', methods = ['GET', 'POST'])
def login():

    message = ""
    test = session.get('myAccount', None)
    if test is not None:
        return redirect(url_for('wallet'))
    if request.method == 'POST':
        print("test2")
        session['myAccount'] = request.form.get('fromAddress')
        return redirect(url_for('wallet'))
    return render_template('login.html', message = message)

@app.route('/logout')
def logout():
    test = session.get('myAccount', None)
    if test is not None:
        session.pop('myAccount', None)
    return redirect(url_for('index'))

@app.route('/wallet', methods = ['GET', 'POST'])
def wallet():
    message = ''
    test = session.get('myAccount', None)
    myacc = accountInfo(test, UTXOS)
    balance = myacc.getBalance()
    if test is None:
        return redirect(url_for('index'))
    if request.method == 'POST' and test is not None:
        print("test")
        FromAddress = test
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

    return render_template('wallet.html', message = message, balance = balance)


def main(utxos, MemPool):
    global UTXOS
    global MEMPOOL
    UTXOS = utxos
    MEMPOOL = MemPool
    app.run()
