# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
import c2w.protocol.constants as constants
import c2w.main.constants as c2w_constants
from c2w.main.lossy_transport import LossyTransport
from c2w.protocol.format_type import FormatType
from c2w.protocol.user import User
from twisted.internet import reactor
import logging

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_server_protocol')


class c2wUdpChatServerProtocol(DatagramProtocol):

    def __init__(self, serverProxy, lossPr):
        """
        :param serverProxy: The serverProxy, which the protocol must use
            to interact with the user and movie store (i.e., the list of users
            and movies) in the server.
        :param lossPr: The packet loss probability for outgoing packets.  Do
            not modify this value!

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: serverProxy

            The serverProxy, which the protocol must use
            to interact with the user and movie store in the server.

        .. attribute:: lossPr

            The packet loss probability for outgoing packets.  Do
            not modify this value!  (It is used by startProtocol.)

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """
        #: The serverProxy, which the protocol must use
        #: to interact with the server (to access the movie list and to 
        #: access and modify the user list).
        self.serverProxy = serverProxy
        self.lossPr = lossPr
        self.format = FormatType()

        # Connected users
        self.connectedUser = {}  # Dictionary of Type: Users
        self.refusedUsers = {}  # Dictionary of Type: Users

    def startProtocol(self):
        """
        DO NOT MODIFY THE FIRST TWO LINES OF THIS METHOD!!

        If in doubt, do not add anything to this method.  Just ignore it.
        It is used to randomly drop outgoing packets if the -l
        command line option is used.
        """
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport

    def datagramReceived(self, datagram, host_port):
        """
        :param string datagram: the payload of the UDP packet.
        :param host_port: a touple containing the source IP address and port.
        
        Twisted calls this method when the server has received a UDP
        packet.  You cannot change the signature of this method.
        """

        [longueur, num_sequence, type, info] = self.format.datagram_received(datagram)

        # User id
        userId = str(host_port[0]) + ':' + str(host_port[1])

        # If the server receives a different type than 0 -> Always send the ACK
        if type != 0:
            pack = self.format.msg_acquittemen(num_sequence)
            self.transport.write(pack, host_port)

        if type == 0:
            # Get the User object
            user = None
            if userId in self.connectedUser:
                user = self.connectedUser[userId]
            elif userId in self.refusedUsers:
                user = self.refusedUsers[userId]

            if user is not None:
                if num_sequence == user.emissionCounter:
                    # Set message as sended to stop the resend
                    user.waitingMessages[num_sequence].sendedStatus = True
                    user.emissionCounter += 1

                    # Delete message if it was sent
                    user.deleteMessage(num_sequence)
                    if len(user.waitingMessages) > 0:
                        self.controlPackages(userId, user.emissionCounter)

        if type != 0 and userId in self.connectedUser:
            if num_sequence == self.connectedUser[userId].receptionCounter:
                self.connectedUser[userId].receptionCounter += 1

                # Format Type 2 : Quitter Application
                if type == 2:
                    self.serverProxy.removeUser(self.connectedUser[userId].username)
                    del self.connectedUser[userId]
                    self.sendUsersToRoom(c2w_constants.ROOM_IDS.MAIN_ROOM)

                # Type 3: Choix d’un film
                if type == 3:
                    self.serverProxy.updateUserChatroom(self.connectedUser[userId].username, info)
                    self.serverProxy.startStreamingMovie(info)

                    userName = self.connectedUser[userId].username
                    movie = self.serverProxy.getUserByName(userName).userChatRoom
                    usersInRoom = self.getUsersInRoom(movie)

                    for id in self.connectedUser:
                        userRoom = self.serverProxy.getUserByName(self.connectedUser[id].username).userChatRoom

                        # Update user list in main room
                        if userRoom == c2w_constants.ROOM_IDS.MAIN_ROOM:
                            self.updateMainRoom(id)
                        # Update movie room
                        if userRoom == movie:
                            self.updateMovieRoom(id, usersInRoom)

                # Format 4 : Quitter salon Film
                if type == 4:
                    userName = self.connectedUser[userId].username
                    movie = self.serverProxy.getUserByName(userName).userChatRoom
                    self.serverProxy.stopStreamingMovie(movie)
                    self.serverProxy.updateUserChatroom(userName, c2w_constants.ROOM_IDS.MAIN_ROOM)
                    usersInRoom = self.getUsersInRoom(movie)

                    for id in self.connectedUser:
                        userRoom = self.serverProxy.getUserByName(self.connectedUser[id].username).userChatRoom

                        # Update user list in main room
                        if userRoom == c2w_constants.ROOM_IDS.MAIN_ROOM:
                            self.updateMainRoom(id)
                        # Update movie room
                        if userRoom == movie:
                            self.updateMovieRoom(id, usersInRoom)

                # Format Type 9 : Chat
                if type == 9:
                    # Send the chat message to all users in the same room (but not at the sender user)
                    room = self.serverProxy.getUserByName(self.connectedUser[userId].username).userChatRoom

                    for user in self.connectedUser:
                        userRoom = self.serverProxy.getUserByName(self.connectedUser[user].username).userChatRoom
                        if room == userRoom and userId != user:
                            pack = self.format.msg_chat(self.connectedUser[user].num_sequence,
                                                        info[0], info[1])
                            self.sendPackage(user, pack)

        # Connexion message (Type 1)
        if type == 1:
            # Add user to connected users list
            if not self.serverProxy.userExists(info):
                # Add user to the server users list
                if userId not in self.connectedUser:
                    self.connectedUser[userId] = User(host_port, info)

                user = self.connectedUser[userId]
                # Add user to the server system
                self.serverProxy.addUser(info, c2w_constants.ROOM_IDS.MAIN_ROOM, userChatInstance=None, userAddress=host_port)

                # Send Type 7: Connexion OK
                pack = self.format.msg_acceptation_connexion(user.num_sequence)
                self.connectedUser[userId].addMessage(pack, user.num_sequence)
                self.sendPackage(userId, pack)
                self.connectedUser[userId].receptionCounter += 1

                # Send Type 5: Movie list
                movies = self.serverProxy.getMovieList()
                pack = self.format.msg_liste_des_films(movies, user.num_sequence)
                self.sendPackage(userId, pack)

                # Send Type 6: liste Utilisateurs
                self.sendUsersToRoom(self.serverProxy.getUserByName(self.connectedUser[userId].username).userChatRoom)
            # Refuse connexion
            else:
                # Add user to the refused users list
                if userId not in self.refusedUsers:
                    self.refusedUsers[userId] = User(host_port, info)

                pack = self.format.msg_refus_connexion(num_sequence)
                self.sendPackage(userId, pack)

    def updateMainRoom(self, userId):
        users = self.serverProxy.getUserList()
        pack = self.format.msg_liste_des_utilisateurs(users, self.serverProxy, self.connectedUser[userId].num_sequence)

        self.sendPackage(userId, pack)

    def updateMovieRoom(self, userId, usersInMovieRoom):
        pack = self.format.msg_liste_des_utilisateurs(usersInMovieRoom, self.serverProxy, self.connectedUser[userId].num_sequence)

        self.sendPackage(userId, pack)

    def getUsersInRoom(self, room):
        users = self.serverProxy.getUserList()
        usersInRoom = []

        for user in users:
            if user.userChatRoom == room:
                usersInRoom.append(user)

        return usersInRoom

    def sendUsersToRoom(self, room):
        users = self.serverProxy.getUserList()

        # Send the usernames to all users in the same room
        usersIdsInThisRoom = []
        for userId in self.connectedUser:
            userRoom = self.serverProxy.getUserByName(self.connectedUser[userId].username).userChatRoom
            if room == userRoom:
                usersIdsInThisRoom.append(userId)

        for id in usersIdsInThisRoom:
            pack = self.format.msg_liste_des_utilisateurs(users, self.serverProxy, self.connectedUser[id].num_sequence)
            self.sendPackage(id, pack)

    def sendPackage(self, userId, pack):
        user = None
        if userId in self.connectedUser:
            user = self.connectedUser[userId]
        elif userId in self.refusedUsers:
            user = self.refusedUsers[userId]

        if user is not None:
            user.addMessage(pack, user.num_sequence)
            self.controlPackages(userId, user.num_sequence)
            user.num_sequence += 1

    def controlPackages(self, userId, num_sequence):
        user = None
        if userId in self.connectedUser:
            user = self.connectedUser[userId]
        elif userId in self.refusedUsers:
            user = self.refusedUsers[userId]

        if user is not None:
            if num_sequence == user.emissionCounter:
                if num_sequence in user.waitingMessages:
                    self.transport.write(user.waitingMessages[num_sequence].data, user.host_port)
                    user.waitingMessages[num_sequence].attempsCounter += 1
                    reactor.callLater(1, self.resendPackage, userId, num_sequence)

    def resendPackage(self, userId, num_sequence):
        user = None
        if userId in self.connectedUser:
            user = self.connectedUser[userId]
        elif userId in self.refusedUsers:
            user = self.refusedUsers[userId]

        if user is not None:
            if num_sequence in user.waitingMessages:
                message = user.getMessage(num_sequence)
                # If the message is set as not sended
                if message.sended is False:
                    # If attemps counter <= 7
                    if message.attempsCounter <= constants.MAX_ATTEMPS_RESEND:
                        self.transport.write(message.data, user.host_port)
                        # Increase attemps counter
                        message.attempsCounter += 1
                        # Call this method again
                        reactor.callLater(1, self.resendPackage, userId, num_sequence)
                    elif message.attempsCounter > constants.MAX_ATTEMPS_RESEND and userId in self.connectedUser:
                        movie = self.serverProxy.getUserByName(self.connectedUser[userId].username).userChatRoom
                        usersInRoom = self.getUsersInRoom(movie)
                        self.serverProxy.removeUser(self.connectedUser[userId].username)
                        #: Delete user of the dictionary of users
                        del self.connectedUser[userId]

                        # Update the users lists without this user
                        for id in self.connectedUser:
                            userRoom = self.serverProxy.getUserByName(self.connectedUser[id].username).userChatRoom

                            # Update user list in main room
                            if userRoom == c2w_constants.ROOM_IDS.MAIN_ROOM:
                                self.updateMainRoom(id)
                            # Update movie room
                            if userRoom == movie:
                                self.updateMovieRoom(id, usersInRoom)
