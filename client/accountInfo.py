import hashlib
import os

import base58
import json
import datetime

from flask import jsonify

from Blockchain.backend.util.util import decode_base58
from Blockchain.backend.core.Script import Script
from Blockchain.backend.core.Tx import TxIn, TxOut, Tx
from Blockchain.backend.core.database.database import AccountDB
from Blockchain.backend.core.EllepticCurve.EllepticCurve import PrivateKey
import time


# --- YOUR ACCOUNT/SENDING CLASS (remains unchanged) ---
class accountInfo:
    def __init__(self, fromAccount, UTXOS):
        self.COIN = 1000
        self.FromPublicAddress = fromAccount
        self.utxos = UTXOS

        # Corrected path calculation
        # This will always find 'blockchain' relative to 'accountInfo.py'
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(current_script_dir)  # Go up from 'client' to 'KWH-OTH-Project'
        self.BLOCKCHAIN_DATA_FILE = os.path.join(project_root_dir, 'data', 'blockchain')

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

    def getBalance(self):
        self.Balance = 0
        self.from_address_script_pubkey = self.scriptPubKey(self.FromPublicAddress)
        self.fromPubKeyHash = self.from_address_script_pubkey.cmds[2]

        newutxos = {}
        try:
            while len(newutxos) < 1:
                newutxos = dict(self.utxos)
                if not newutxos:
                    time.sleep(2)
        except Exception as e:
            print(f"Error in converting the Managed Dict to Normal Dict: {e}")

        for Txbyte in newutxos:
            TxObj = newutxos[Txbyte]
            for index, txout in enumerate(TxObj.tx_outs):
                if txout.script_pubkey.cmds[2] == self.fromPubKeyHash:
                    self.Balance += txout.amount
        return self.Balance / self.COIN

    def decode_base58_address(self, address):
        """
        Decodes a Base58 address into its PubKeyHash (hex string).
        Handles potential errors during decoding.
        """
        try:
            decoded = base58.b58decode(address)
            if len(decoded) < 5:
                raise ValueError(
                    f"Invalid Base58 address length after decoding: {len(decoded)} bytes. Expected at least 25 bytes for P2PKH.")
            return decoded[1:-4].hex()
        except ValueError as e:
            print(f"Error decoding Base58 address '{address}': {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during Base58 decoding for address '{address}': {e}")
            return None

    def encode_pubkey_hash_to_address(self, pubkey_hash):
        """
        Encodes a PubKeyHash (hex string) back into a Base58 address.
        This is a simplified version and assumes a Bitcoin-like P2PKH address structure.
        Needs to match your `decode_base58` and `encode_base58_checksum` in your backend.
        """
        try:
            version_byte = b'\x00'  # Or whatever your project uses for its address version
            decoded_pubkey_hash = bytes.fromhex(pubkey_hash)
            full_payload = version_byte + decoded_pubkey_hash
            checksum = hashlib.sha256(hashlib.sha256(full_payload).digest()).digest()[:4]
            return base58.b58encode(full_payload + checksum).decode('utf-8')
        except Exception as e:
            print(f"Error encoding PubKeyHash '{pubkey_hash}' to address: {e}")
            return "Unknown Address"

    def get_transaction_history(self, blockchain_data, target_address):
        """
        Retrieves the transaction history for a given target address from blockchain data,
        including both received and sent transactions, excluding coinbase rewards.
        """
        history = []
        target_pubkey_hash = self.decode_base58_address(target_address)

        if not target_pubkey_hash:
            print(f"Skipping history retrieval for address '{target_address}' due to invalid address decoding.")
            return []

        print(f"Retrieving transaction history for address: {target_address} (PubKeyHash: {target_pubkey_hash})\n")

        # Create a quick lookup for transaction outputs by TxId for resolving inputs
        tx_output_lookup = {}
        for block in blockchain_data:
            for tx in block["Txs"]:
                tx_id = tx["TxId"]
                if tx_id not in tx_output_lookup:
                    tx_output_lookup[tx_id] = {}
                for idx, tx_out in enumerate(tx["tx_outs"]):
                    tx_output_lookup[tx_id][idx] = tx_out

        for block in blockchain_data:
            block_height = block["Height"]
            block_hash = block["BlockHeader"]["blockHash"]
            timestamp_dt = datetime.datetime.fromtimestamp(block["BlockHeader"]["timestamp"])

            for tx in block["Txs"]:
                tx_id = tx["TxId"]
                is_coinbase = tx["tx_ins"][0][
                                  "prev_tx"] == "0000000000000000000000000000000000000000000000000000000000000000" and \
                              tx["tx_ins"][0]["prev_index"] == 4294967295

                # --- Check for RECEIVED Transactions ---
                # Exclude coinbase rewards here
                if not is_coinbase:  # <--- Added this condition
                    for tx_out_index, tx_out in enumerate(tx["tx_outs"]):
                        script_pubkey_cmds = tx_out["script_pubkey"]["cmds"]
                        if len(script_pubkey_cmds) == 5 and script_pubkey_cmds[2].lower() == target_pubkey_hash.lower():
                            amount_satoshi = tx_out["amount"]
                            amount_btc_display = amount_satoshi / 100_000_000
                            transaction_type = "Received"  # Removed "Coinbase Reward"
                            history.append({
                                "Block Height": block_height,
                                "Block Hash": block_hash,
                                "Timestamp": timestamp_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                "TxId": tx_id,
                                "Type": transaction_type,
                                "Amount (Satoshi)": amount_satoshi,
                                "Amount (BTC)": f"{amount_btc_display:.8f}",
                                "Address": target_address,
                                "To/From": "Received By You",
                                "Tx Output Index": tx_out_index
                            })

                # --- Check for SENT Transactions (if not a coinbase, as coinbase has no sender) ---
                if not is_coinbase:
                    is_sender = False
                    total_input_amount = 0
                    sender_address = "Unknown Sender"

                    for tx_in in tx["tx_ins"]:
                        prev_tx_id = tx_in["prev_tx"]
                        prev_output_index = tx_in["prev_index"]

                        if prev_tx_id in tx_output_lookup and prev_output_index in tx_output_lookup[prev_tx_id]:
                            prev_tx_out = tx_output_lookup[prev_tx_id][prev_output_index]
                            prev_script_pubkey_cmds = prev_tx_out["script_pubkey"]["cmds"]
                            if len(prev_script_pubkey_cmds) == 5 and prev_script_pubkey_cmds[
                                2].lower() == target_pubkey_hash.lower():
                                is_sender = True
                                total_input_amount += prev_tx_out["amount"]
                                sender_address = target_address

                    if is_sender:
                        for tx_out_index, tx_out in enumerate(tx["tx_outs"]):
                            recipient_script_pubkey_cmds = tx_out["script_pubkey"]["cmds"]
                            if len(recipient_script_pubkey_cmds) == 5:
                                recipient_pubkey_hash = recipient_script_pubkey_cmds[2]
                                if recipient_pubkey_hash.lower() != target_pubkey_hash.lower():
                                    recipient_address = self.encode_pubkey_hash_to_address(recipient_pubkey_hash)
                                    amount_satoshi = tx_out["amount"]
                                    amount_btc_display = amount_satoshi / 100_000_000

                                    history.append({
                                        "Block Height": block_height,
                                        "Block Hash": block_hash,
                                        "Timestamp": timestamp_dt.strftime('%Y-%m-%d %H:%M:%S'),
                                        "TxId": tx_id,
                                        "Type": "Sent",
                                        "Amount (Satoshi)": amount_satoshi,
                                        "Amount (BTC)": f"{amount_btc_display:.8f}",
                                        "Address": sender_address,
                                        "To/From": f"Sent To {recipient_address}",
                                        "Tx Output Index": tx_out_index
                                    })

        return history

    def get_address_history(self, address):
        """
        API endpoint to retrieve transaction history for a given address.
        Accessed via GET request: /history/<address>
        Example: http://localhost:5000/history/1LWxEfevJUFv73hVGmqJ72ZwfqYv1GzMUk
        """
        BLOCKCHAIN_DATA_FILE = '../data/blockchain'
        blockchain_data = []
        print(f"Attempting to load blockchain data from: {self.BLOCKCHAIN_DATA_FILE}")
        try:
            with open(self.BLOCKCHAIN_DATA_FILE, 'r') as f:
                blockchain_data = json.load(f)
            print("Blockchain data loaded successfully.")
        except FileNotFoundError:
            print(f"Error: The file '{self.BLOCKCHAIN_DATA_FILE}' was not found.")
            print("Please ensure the file exists at the path '../data/blockchain' relative to the script.")
        except json.JSONDecodeError as e:
            print(f"Error: Could not decode JSON from '{self.BLOCKCHAIN_DATA_FILE}'. Please check the file format.")
            print(f"Details of the JSON decoding error: {e}")
            print(
                "Ensure the content of the 'blockchain' file is valid JSON (e.g., all keys and strings in double quotes, proper commas).")
        except Exception as e:
            print(f"An unexpected error occurred while loading blockchain data: {e}")
        # Check if blockchain data was loaded successfully
        if not blockchain_data:
            return jsonify({"error": "Blockchain data not loaded. Please check server logs for details."}), 500

        history = self.get_transaction_history(blockchain_data, address)

        if not history:
            # If no transactions are found for a valid address, return an empty list with 200 OK
            # This signifies the request was processed successfully, but no relevant data exists.
            return jsonify({"message": f"No transactions found for address '{address}'.", "history": []}), 200
        else:
            # Return the found history as a JSON array
            return jsonify(history), 200


# --- STANDALONE UTILITY FUNCTIONS ---



# --- MAIN SCRIPT EXECUTION BLOCK (remains unchanged) ---
# if __name__ == "__main__":
#     BLOCKCHAIN_DATA_FILE = '../data/blockchain'
#     MINER_ADDRESS = '1LWxEfevJUFv73hVGmqJ72ZwfqYv1GzMUk'
#
#     blockchain_data = []
#     print(f"Attempting to load blockchain data from: {BLOCKCHAIN_DATA_FILE}")
#     try:
#         with open(BLOCKCHAIN_DATA_FILE, 'r') as f:
#             blockchain_data = json.load(f)
#         print("Blockchain data loaded successfully.")
#     except FileNotFoundError:
#         print(f"Error: The file '{BLOCKCHAIN_DATA_FILE}' was not found.")
#         print("Please ensure the file exists at the path '../data/blockchain' relative to the script.")
#     except json.JSONDecodeError as e:
#         print(f"Error: Could not decode JSON from '{BLOCKCHAIN_DATA_FILE}'. Please check the file format.")
#         print(f"Details of the JSON decoding error: {e}")
#         print("Ensure the content of the 'blockchain' file is valid JSON (e.g., all keys and strings in double quotes, proper commas).")
#     except Exception as e:
#         print(f"An unexpected error occurred while loading blockchain data: {e}")
#
#     if blockchain_data:
#         history = get_transaction_history(blockchain_data, MINER_ADDRESS)
#
#         if history:
#             print("\n--- Transaction History ---")
#             history.sort(key=lambda x: (x['Block Height'], datetime.datetime.strptime(x['Timestamp'], '%Y-%m-%d %H:%M:%S')))
#
#             for entry in history:
#                 print(f"Block: {entry['Block Height']} (Hash: {entry['Block Hash'][:8]}...)")
#                 print(f"  TxId: {entry['TxId'][:8]}...")
#                 print(f"  Type: {entry['Type']}")
#                 print(f"  Amount: {entry['Amount (BTC)']} BTC ({entry['Amount (Satoshi)']} Satoshis)")
#                 print(f"  {entry['To/From']}")
#                 print(f"  Timestamp: {entry['Timestamp']}")
#                 print("-" * 30)
#         else:
#             print(f"\nNo non-coinbase transactions found for address '{MINER_ADDRESS}' in the loaded blockchain data.")
#     else:
#         print("\nBlockchain data could not be loaded, so no transaction history is available.")