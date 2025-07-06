import sys
sys.path.append('/Users/Jonny/Downloads/KWH-OTH/KWH-OTH-Project')
from Blockchain.backend.core.EllipticCurve.EllipticCurve import Sha256Point, BASE58_ALPHABET
from Blockchain.backend.util.util import hash160, hash256
from Blockchain.backend.core.database.database import AccountDB
import secrets


class account:
    def createKeys(self):
        Gx = 0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798
        Gy = 0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8

        G = Sha256Point(Gx, Gy)

        self.privateKey = secrets.randbits(256)
        unCompressedPublicKey = self.privateKey * G
        xpoint= unCompressedPublicKey.x
        ypoint = unCompressedPublicKey.y

        if ypoint.num % 2 == 0:
            compressesKey = b'\x02' + xpoint.num.to_bytes(32, 'big')
        else:
            compressesKey = b'\x03' + xpoint.num.to_bytes(32, 'big')

        hsh160 = hash160(compressesKey)
        #Prefix for Mainnet
        main_prefix = b'\x00'

        newAddr = main_prefix + hsh160

        checksum = hash256(newAddr)[:4]

        newAddr = newAddr + checksum
        BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

        count = 0

        for c in newAddr:
            if c == 0:
                count += 1
            else:
                break

        num = int.from_bytes(newAddr, 'big')
        prefix = '1' * count

        result = ''


        while num > 0:
            num, mod = divmod(num, 58)
            result = BASE58_ALPHABET[mod] + result

        self.PublicAddress = prefix + result

        print(f"Private Key {self.privateKey}")
        print(f"Public Key {self.PublicAddress}")
        print(f"Xpoint {xpoint} \n Ypoint {ypoint}")



if __name__ == "__main__":
    acct = account()
    acct.createKeys()
    AccountDB().write([acct.__dict__])