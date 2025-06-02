import json
import os


class BaseDB:
    def __init__(self):
        self.basepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../data"))
        os.makedirs(self.basepath, exist_ok=True)
        self.filepath = '/'.join((self.basepath, self.filename))

    def read(self):
        if not os.path.exists(self.filepath):
            print(f"File {self.filepath} doesn't exist")
            return False

        with open(self.filepath,'r') as file:
            raw = file.readline()

        if len(raw) > 0:
            data = json.loads(raw)
        else:
            data = []
        return data

    def write(self, item):

        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

        data = self.read()
        if data:
            data = data + item
        else:
            data = item

        with open(self.filepath, 'w+') as file:
            file.write(json.dumps(data))

class BlockchainDB(BaseDB):
    def __init__(self):
        self.filename = 'blockchain'
        super().__init__()

    def lastBlock(self):
        data = self.read()

        if data:
            return data[-1]

class AccountDB(BaseDB):
    def __init__(self):
        self.filename = 'account'
        super().__init__()