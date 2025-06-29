# W:\Energieinformatik\KWH-OTH-Project\Blockchain\frontend\run.py

from flask import Flask, render_template, request, session, redirect, url_for
import multiprocessing  # Erforderlich, wenn Manager().dict() für UTXOS/MEMPOOL verwendet wird
import json
from client.accountInfo import accountInfo
from client.sendKWH import SendKWH

app = Flask(__name__)

app.secret_key = 'BAD_SECRET_KEY'

# Globale Variablen für den geteilten Zustand
UTXOS = None
MEMPOOL = None


# REMOVED: GLOBAL_WALLET = None # Nicht mehr benötigt, da keine Wallet-Klasse verwendet wird

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    return render_template('index.html', message=message)


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

    # Sicherstellen, dass globale Variablen initialisiert sind
    # GLOBAL_WALLET Check ist nicht mehr nötig
    if UTXOS is None or MEMPOOL is None:
        message = "System nicht vollständig initialisiert. Bitte neu starten oder Blockchain-Startup prüfen."
        return render_template('wallet.html', message=message, balance=0)

    myacc = accountInfo(current_user_address, UTXOS)
    balance = myacc.getBalance()

    if request.method == 'POST':
        print("test")
        ToAddress = request.form.get('toAddress')
        Amount = request.form.get('Amount', type=int)

        # Instanziiere SendKWH mit den Transaktionsdetails und den globalen UTXOs
        # Die `SendKWH` Klasse holt sich den privaten Schlüssel selbst aus der `AccountDB`.
        send_kwh_processor = SendKWH(current_user_address, ToAddress, Amount, UTXOS)

        # Bereite die Transaktion vor
        TxObj = send_kwh_processor.prepareTransaction()

        # Überprüfe, ob prepareTransaction erfolgreich war (gibt False bei Fehlern zurück)
        if TxObj is False:
            message = "Transaktion konnte nicht erstellt werden: Unzureichendes Guthaben, Schlüssel nicht gefunden oder anderer Fehler. Details in den Server-Logs."
            print(
                f"ERROR (run.py): Transaktionsvorbereitung fehlgeschlagen für {current_user_address} -> {ToAddress}, {Amount}.")
        else:
            verified = True
            # Der sender_script_pubkey wird von der send_kwh_processor Instanz selbst erzeugt
            sender_script_pubkey = send_kwh_processor.scriptPubKey(current_user_address)

            if sender_script_pubkey:
                for index, tx_in_to_verify in enumerate(TxObj.tx_ins):
                    # WICHTIG: Deine Tx.verify_input Methode muss in der Lage sein,
                    # die Signatur mit dem ursprünglichen script_pubkey des ausgegebenen Outputs
                    # zu prüfen. Wenn sie nur den `sender_script_pubkey` als Argument nimmt,
                    # muss sie intern auf die UTXO-Informationen zugreifen, um den richtigen
                    # script_pubkey zu finden.
                    if not TxObj.verify_input(index, sender_script_pubkey):  # Dies ist ein Annahmepunkt.
                        verified = False
                        print(f"ERROR (run.py): Verifizierung von Input {index} fehlgeschlagen.")
                        break
            else:
                verified = False
                print(
                    f"ERROR (run.py): Sender's script_pubkey konnte für Verifizierung nicht generiert werden: {current_user_address}")

            if verified:
                MEMPOOL[TxObj.TxId] = TxObj  # TxObj.TxId ist bereits der Hex-String
                message = "Transaktion erfolgreich im MemoryPool hinzugefügt!"
                print(f"DEBUG (run.py): Transaktion {TxObj.TxId} erfolgreich im MemPool.")
            else:
                message = "Transaktion Verifizierung fehlgeschlagen! Wird nicht zum MemoryPool hinzugefügt."
                print(f"ERROR (run.py): Transaktion {TxObj.TxId} Verifizierung fehlgeschlagen.")

    return render_template('wallet.html', message = message, balance = balance, transactionHistory = transaction_history_data)


def main(utxos, MemPool):
    global UTXOS
    global MEMPOOL
    # REMOVED: global GLOBAL_WALLET # Nicht mehr benötigt

    UTXOS = utxos  # Dies ist das multiprocessing.Manager().dict()
    MEMPOOL = MemPool  # Dies ist das multiprocessing.Manager().dict()
    # REMOVED: GLOBAL_WALLET = Wallet() # Nicht mehr benötigt

    app.run()  # Starte die Flask-App