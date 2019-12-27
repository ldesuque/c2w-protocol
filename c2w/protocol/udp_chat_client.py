# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
import c2w.main.constants as c2w_constants
import c2w.protocol.constants as constants
from twisted.internet import reactor
from c2w.protocol.message import Message
from c2w.protocol.format_type import FormatType
import logging

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_client_protocol')


class c2wUdpChatClientProtocol(DatagramProtocol):

    def __init__(self, serverAddress, serverPort, clientProxy, lossPr):
        """
        :param serverAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param serverPort: The port number used by the c2w server,
            given by the user.
        :param clientProxy: The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attributes:

        .. attribute:: serverAddress

            The IP address of the c2w server.

        .. attribute:: serverPort

            The port number of the c2w server.

        .. attribute:: clientProxy

            The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        .. attribute:: lossPr

            The packet loss probability for outgoing packets.  Do
            not modify this value!  (It is used by startProtocol.)

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """

        #: The IP address of the c2w server.
        self.serverAddress = serverAddress
        #: The port number of the c2w server.
        self.serverPort = serverPort
        #: The clientProxy, which the protocol must use
        #: to interact with the Graphical User Interface.
        self.clientProxy = clientProxy
        self.lossPr = lossPr

        self.format = FormatType()

        # Dictionary of Type Message
        self.waitingMessages = {}

        # Emission counter
        self.emissionCounter = 0
        # Received counter
        self.receivedCounter = 0
        # Message number in the header of the messages
        self.numMessage = 0

        # Users list
        self.usersConnected = {}
        self.room = None
        self.movies = []

        self.mainRoom = True
        self.firstLogin = True
        self.userName = None

    def startProtocol(self):
        """
        DO NOT MODIFY THE FIRST TWO LINES OF THIS METHOD!!

        If in doubt, do not add anything to this method.  Just ignore it.
        It is used to randomly drop outgoing packets if the -l
        command line option is used.
        """
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport

    def sendLoginRequestOIE(self, userName):
        """
        :param string userName: The user name that the user has typed.

        The client proxy calls this function when the user clicks on
        the login button.
        """
        moduleLogger.debug('loginRequest called with username=%s', userName)
        self.userName = userName
        pack = self.format.msg_connexion(self.numMessage, userName)

        self.sendPackage(pack, 1)

    def sendChatMessageOIE(self, message):
        """
        :param message: The text of the chat message.
        :type message: string

        Called by the client proxy  when the user has decided to send
        a chat message

        .. note::
           This is the only function handling chat messages, irrespective
           of the room where the user is.  Therefore it is up to the
           c2wChatClientProctocol or to the server to make sure that this
           message is handled properly, i.e., it is shown only by the
           client(s) who are in the same room.
        """
        self.numMessage += 1
        pack = self.format.msg_chat(self.numMessage, self.userName, message)
        self.sendPackage(pack, 9)

    def sendJoinRoomRequestOIE(self, roomName):
        """
        :param roomName: The room name (or movie title.)

        Called by the client proxy  when the user
        has clicked on the watch button or the leave button,
        indicating that she/he wants to change room.

        .. warning:
            The controller sets roomName to
            c2w.main.constants.ROOM_IDS.MAIN_ROOM when the user
            wants to go back to the main room.
        """

        self.numMessage += 1
        if roomName == c2w_constants.ROOM_IDS.MAIN_ROOM:
            message = self.format.msg_quitter_salon(self.numMessage)
            self.sendPackage(message, 4)

        else:
            message = self.format.msg_selection_film(self.numMessage, roomName)
            self.sendPackage(message, 3)
            self.room = roomName

    def sendLeaveSystemRequestOIE(self):
        """
        Called by the client proxy  when the user
        has clicked on the leave button in the main room.
        """
        self.numMessage += 1
        message = self.format.msg_quitter_app(self.numMessage)
        self.sendPackage(message, 2)

    def datagramReceived(self, datagram, host_port):
        """
        :param string datagram: the payload of the UDP packet.
        :param host_port: a touple containing the source IP address and port.

        Called **by Twisted** when the client has received a UDP
        packet.
        """

        [longueur, num_sequence, type, message] = self.format.datagram_received(datagram)

        # If the client receives a different type than 0 -> Always send the ACK
        if type != 0:
            pack = self.format.msg_acquittemen(num_sequence)
            self.transport.write(pack, host_port)

        if type == 0:
            if num_sequence == self.emissionCounter:
                # Set the message as sended
                self.waitingMessages[num_sequence].sended = True
                self.emissionCounter += 1

                # Format Type 2 : Quitter Application
                if self.waitingMessages[self.numMessage].type == 2:
                    self.clientProxy.leaveSystemOKONE()

                # Format 3: Selection du Film
                if self.waitingMessages[self.numMessage].type == 3:
                    self.clientProxy.joinRoomOKONE()
                    self.mainRoom = False

                # Format 4 : Quitter salon Film
                if self.waitingMessages[self.numMessage].type == 4:
                    self.clientProxy.joinRoomOKONE()
                    self.mainRoom = True

                # Delete message if it was sent
                del self.waitingMessages[num_sequence]
                if bool(self.waitingMessages):
                    self.controlPackages(self.emissionCounter)

        if num_sequence == self.receivedCounter and type != 0:
            self.receivedCounter += 1
            # Format Type 7 : Acceptation connexion
            if type == 7:
                self.room = c2w_constants.ROOM_IDS.MAIN_ROOM
                self.usersConnected[host_port] = []

            # Type 5: liste des films
            if type == 5:
                self.movies = self.format.get_movie_list(message)

            # Type 6: liste Utilisateurs
            if type == 6:
                self.usersConnected[host_port] = self.format.get_user_list(message)
                # I have the movies and users!

                if self.mainRoom:  # The user is in the main room
                    self.clientProxy.setUserListONE([])
                    if not self.firstLogin:
                        self.clientProxy.setUserListONE(self.usersConnected[host_port])
                    else:
                        self.clientProxy.initCompleteONE(self.usersConnected[host_port], self.movies)
                        self.firstLogin = False

                else:  # The user is in the movie room
                    self.clientProxy.setUserListONE([])
                    for user in self.usersConnected[host_port]:
                        self.clientProxy.userUpdateReceivedONE(user[0], self.room)

            # Format Type 8 : Refus de connexion
            if type == 8:
                self.clientProxy.connectionRejectedONE("Un utilisateur avec ce nom existe déjà")

            # Format 9 : Chat
            if type == 9:
                self.clientProxy.chatMessageReceivedONE(message[0], message[1])

    def sendPackage(self, pack, type):
        message = Message(pack, type)
        self.waitingMessages[self.numMessage] = message

        self.controlPackages(self.numMessage)

    def controlPackages(self, num_sequence):
        if num_sequence == self.emissionCounter:
            # Send the message
            self.transport.write(self.waitingMessages[num_sequence].data, (self.serverAddress, self.serverPort))
            # Increase emission counter
            self.waitingMessages[num_sequence].attempsCounter += 1
            # Reemission message
            reactor.callLater(1, self.resendPackage, num_sequence)

    def resendPackage(self, num_sequence):
        if num_sequence in self.waitingMessages:
            message = self.waitingMessages[num_sequence]
            # If the message is set as not sended
            if message.sended is False:
                # If attemps counter <= 7
                if message.attempsCounter <= constants.MAX_ATTEMPS_RESEND:
                    self.transport.write(message.data, (self.serverAddress, self.serverPort))
                    # Increase attemps counter
                    message.attempsCounter += 1

                    # Call this method again
                    reactor.callLater(1, self.resendPackage, num_sequence)
                else:
                    self.clientProxy.connectionRejectedONE("Connection rejected")
                    self.clientProxy.applicationQuit()
