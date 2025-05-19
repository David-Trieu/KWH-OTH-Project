from flask import Flask, render_template, request

#from Blockcain.client.sendKWH import sendKWH

app = Flask(__name__)

@app.route('/', methods = ['GET', 'POST'])
def wallet():
   # if request.method == 'POST':
   #     FromAddress = request.form.get('fromAddress')
   #     ToAddress = request.form.get('toAddress')
   #     Amount = request.form.get('Amount', type = int)
   #     sendCoin = SendKWH(FromAddress, ToAddress, Amount)
   #
   #     if not sendCoin.prepareTransaction():
   #         message = "Insufficient Balance"
    message = ""
    return render_template('wallet.html', message = message)

#def main(utxos):
    #global UTXOS
    #UTXOS = utxos
if __name__ == '__main__':
    app.run()

#12 ab minute 10 weiter machen
#Import multiprocessing import Process, Manager in blockchain.py