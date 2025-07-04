import re
from client.account import account

def test_public_address_bitcoin_format():
    acct = account()
    acct.createKeys()
    public_address = acct.PublicAddress
    print(f"Generated Public Address: {acct.PublicAddress}")
    assert isinstance(public_address, str)
    min_length = 26
    max_length = 35
    assert len(public_address) >= min_length
    assert len(public_address) <= max_length

    assert public_address.startswith('1')

    pattern = r"^[1-9a-km-zA-HJ-NP-Z]+$"
    assert re.match(pattern, public_address)

    print("Public Address Bitcoin Format Test: ERFOLGREICH BESTANDEN!")

