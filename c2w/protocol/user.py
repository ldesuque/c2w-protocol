from c2w.protocol.message import Message


class User:

    def __init__(self, host_port, username):
        self.host_port = host_port
        self.emissionCounter = 0
        self.receptionCounter = 0
        self.num_sequence = 0
        self.username = username
        self.waitingMessages = {}  # Dictionary of Type Message
        self.userChatInstance = None

    def getMessage(self, num_sequence):
        if num_sequence in self.waitingMessages:
            return self.waitingMessages[num_sequence]
        return None

    def addMessage(self, data, num_sequence):
        self.waitingMessages[num_sequence] = Message(data)

    def deleteMessage(self, num_sequence):
        if num_sequence in self.waitingMessages:
            del self.waitingMessages[num_sequence]

    def setUserChatInstance(self, userChatInstance):
        self.userChatInstance = userChatInstance
