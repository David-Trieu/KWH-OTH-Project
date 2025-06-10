from flask import Flask, render_template, request

from client.sendKWH import SendKWH

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

        if not sendCoin.prepareTransaction():
            message = "Insufficient Balance"
    return render_template('wallet.html', message = message)


def main(utxos):
    global UTXOS
    UTXOS = utxos
    app.run()
