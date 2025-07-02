# W:\Energieinformatik\KWH-OTH-Project\Blockchain\frontend\run.py

from flask import Flask, render_template, request, session, redirect, url_for
import json

from Blockchain.backend.core.database.database import AccountDB
from client.account import account
from client.accountInfo import accountInfo
from client.sendKWH import SendKWH
from waitress import serve

app = Flask(__name__)

app.secret_key = 'BAD_SECRET_KEY'

UTXOS = None
MEMPOOL = None



@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    return render_template('index.html', message=message)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    print("signup")
    acct = account()
    acct.createKeys()
    try:
        # Save the account details using AccountDB
        AccountDB().write([acct.__dict__])
        session['myAccount'] = acct.PublicAddress
        message = "Hier ist deine Wallet-Adresse. \n Bitte schreibe sie dir auf. \n" + acct.PublicAddress
    except Exception as e:
        message = f"Error creating account: {e}"
        print(f"Database write error: {e}")
    return render_template('signup.html', message=message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ""
    test = session.get('myAccount', None)
    if test is not None:
        return redirect(url_for('wallet'))
    if request.method == 'POST':
        print("test2")
        session['myAccount'] = request.form.get('fromAddress')
        return redirect(url_for('wallet'))
    return render_template('login.html', message=message)


@app.route('/logout')
def logout():
    test = session.get('myAccount', None)
    if test is not None:
        session.pop('myAccount', None)
    return redirect(url_for('index'))


@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    message = ''
    current_user_address = session.get('myAccount', None)

    test = session.get('myAccount', None)
    myacc = accountInfo(test, UTXOS)
    try:
        balance = myacc.getBalance()
    except ValueError:
        return render_template('login.html', message="Diese Adresse existiert nicht")
    transactionHistory, code = myacc.get_address_history(test)

    print(json.dumps(transactionHistory.json, indent=4))
    print(code)

    if code == 200:
        parsed_json_data = None
        if hasattr(transactionHistory, 'json') and transactionHistory.json is not None:
            parsed_json_data = transactionHistory.json
        elif hasattr(transactionHistory, 'get_json') and transactionHistory.get_json() is not None:
            parsed_json_data = transactionHistory.get_json()
        else:
            try:
                parsed_json_data = json.loads(transactionHistory.get_data(as_text=True))
            except Exception as e:
                print(f"Fehler beim Decodieren der Transaktionshistorie JSON aus den Response-Daten: {e}")

        if parsed_json_data is not None:
            if isinstance(parsed_json_data, list):
                transaction_history_data = parsed_json_data
            elif isinstance(parsed_json_data, dict) and "history" in parsed_json_data:
                transaction_history_data = parsed_json_data["history"]
            else:
                print(f"Unerwartete JSON-Struktur für erfolgreiche Antwort: {parsed_json_data}")
                transaction_history_data = []
    else:
        error_msg = transactionHistory.get_data(as_text=True) if transactionHistory else "Keine Antwortdaten"
        print(f"Fehler beim Abrufen der Transaktionshistorie: Status {transactionHistory}, Antwort: {error_msg}")
        transaction_history_data = []


    if test is None:
        return redirect(url_for('index'))

    if UTXOS is None or MEMPOOL is None:
        message = "System nicht vollständig initialisiert. Bitte neu starten oder Blockchain-Startup prüfen."
        return render_template('wallet.html', message=message, balance=0)

    myacc = accountInfo(current_user_address, UTXOS)
    balance = myacc.getBalance()

    if request.method == 'POST':
        print("test")
        ToAddress = request.form.get('toAddress')
        Amount = request.form.get('Amount', type=int)

        send_kwh_processor = SendKWH(current_user_address, ToAddress, Amount, UTXOS)

        TxObj = send_kwh_processor.prepareTransaction()

        if TxObj is False:
            message = "Transaktion konnte nicht erstellt werden: Unzureichendes Guthaben, Schlüssel nicht gefunden oder anderer Fehler. Details in den Server-Logs."
            print(
                f"ERROR (run.py): Transaktionsvorbereitung fehlgeschlagen für {current_user_address} -> {ToAddress}, {Amount}.")
        else:
            verified = True
            sender_script_pubkey = send_kwh_processor.scriptPubKey(current_user_address)

            if sender_script_pubkey:
                for index, tx_in_to_verify in enumerate(TxObj.tx_ins):
                    if not TxObj.verify_input(index, sender_script_pubkey):  # Dies ist ein Annahmepunkt.
                        verified = False
                        print(f"ERROR (run.py): Verifizierung von Input {index} fehlgeschlagen.")
                        break
            else:
                verified = False
                print(
                    f"ERROR (run.py): Sender's script_pubkey konnte für Verifizierung nicht generiert werden: {current_user_address}")

            if verified:
                MEMPOOL[TxObj.TxId] = TxObj
                message = "Transaktion erfolgreich im MemoryPool hinzugefügt!"
                print(f"DEBUG (run.py): Transaktion {TxObj.TxId} erfolgreich im MemPool.")
            else:
                message = "Transaktion Verifizierung fehlgeschlagen! Wird nicht zum MemoryPool hinzugefügt."
                print(f"ERROR (run.py): Transaktion {TxObj.TxId} Verifizierung fehlgeschlagen.")

    return render_template('wallet.html', message = message, balance = balance, transactionHistory = transaction_history_data)


def main(utxos, MemPool):
    global UTXOS
    global MEMPOOL
    UTXOS = utxos
    MEMPOOL = MemPool

    print("Starte Flask-App mit Waitress auf http://127.0.0.1:5000 \n")
    serve(app, host='127.0.0.1', port=5000, threads=8)