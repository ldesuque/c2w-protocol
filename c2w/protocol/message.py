class Message:

    def __init__(self, data, type = None):
        self.sended = False
        self.data = data
        self.attempsCounter = 1
        self.type = type
