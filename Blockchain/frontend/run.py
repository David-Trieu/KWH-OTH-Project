from flask import Flask, render_template, request, session, redirect, url_for
import json

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
    transactionHistory, code = myacc.get_address_history(test)

    print(json.dumps(transactionHistory.json, indent=4))
    print(code)
    # THIS IS THE CRUCIAL PART: Extract the actual data from the response_obj

    if code == 200:
        parsed_json_data = None
        # Versuche, die JSON-Daten aus dem Response-Objekt zu extrahieren
        if hasattr(transactionHistory, 'json') and transactionHistory.json is not None:
            parsed_json_data = transactionHistory.json
        elif hasattr(transactionHistory, 'get_json') and transactionHistory.get_json() is not None:
            parsed_json_data = transactionHistory.get_json()
        else:
            # Fallback für den Fall, dass .json oder .get_json() nicht verfügbar sind
            try:
                parsed_json_data = json.loads(transactionHistory.get_data(as_text=True))
            except Exception as e:
                print(f"Fehler beim Decodieren der Transaktionshistorie JSON aus den Response-Daten: {e}")

        if parsed_json_data is not None:
            if isinstance(parsed_json_data, list):
                # Wenn die Antwort direkt eine Liste von Transaktionen ist (Erfolgreicher Fall mit Daten)
                transaction_history_data = parsed_json_data
            elif isinstance(parsed_json_data, dict) and "history" in parsed_json_data:
                # Wenn die Antwort ein Dictionary ist, das einen "history"-Schlüssel enthält
                # Dies deckt den Fall ab, wenn keine Transaktionen gefunden wurden: {"history": [], "message": "..."}
                transaction_history_data = parsed_json_data["history"]
            else:
                # Unerwartete, aber erfolgreiche JSON-Struktur (z.B. wenn es ein Dict ohne "history" ist)
                print(f"Unerwartete JSON-Struktur für erfolgreiche Antwort: {parsed_json_data}")
                transaction_history_data = [] # Standardmäßig auf leere Liste setzen
    else:
        # Wenn get_address_history einen Fehler-Statuscode zurückgegeben hat
        error_msg = transactionHistory.get_data(as_text=True) if transactionHistory else "Keine Antwortdaten"
        print(f"Fehler beim Abrufen der Transaktionshistorie: Status {transactionHistory}, Antwort: {error_msg}")
        transaction_history_data = [] # Standardmäßig auf leere Liste setzen bei Fehler


    #print(json.dumps(transactionHistory.json, indent=2))
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

    return render_template('wallet.html', message = message, balance = balance, transactionHistory = transaction_history_data)


def main(utxos, MemPool):
    global UTXOS
    global MEMPOOL
    UTXOS = utxos
    MEMPOOL = MemPool
    app.run()
