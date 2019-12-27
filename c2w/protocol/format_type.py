# -*- coding: utf-8 -*-
import struct
import c2w.protocol.constants as constants
import c2w.main.constants as c2w_constants


class FormatType:
    
    def __init__(self):
        self.tcpData = bytearray()
        self.messageComplete = False

    @staticmethod
    def value_to_bit(value, long):
            return format(value, 'b').zfill(long)

    def datagram_received(self, datagram):
        # Longueur | Numero Sequence | Type | Message

        lenData = len(datagram) - constants.SIZE_ENTETE
        data = struct.unpack_from('>HH' + str(lenData) + 's', datagram)
        entete_info = hex(int(self.value_to_bit(data[1], constants.SIZE_NUMERO_SEQUENCE + constants.SIZE_TYPE), 2))

        longueur = data[0]
        num_sequence = int(entete_info, 16) >> 4
        type = int(entete_info, 16) & 0xF
        message = None

        if type == 1 or type == 3:
            message = data[2].decode('utf-8')
        if type == 5 or type == 6:
            message = data[2]
        if type == 9:
            lenPseudo = struct.unpack('>B', data[2][0:1])[0]
            data = struct.unpack_from('>B' + str(lenPseudo) + 's' + str(len(data[2])-lenPseudo-1) + 's', data[2])
            message = [data[1].decode('utf-8'), data[2].decode('utf-8')]

        return longueur, num_sequence, type, message

    def isMessageComplete(self):
        return self.messageComplete

    def datagram_received_tcp(self, data):
        self.tcpData += data
        if len(self.tcpData) >= 2:
            messageLen = int.from_bytes(self.tcpData[0:2], byteorder='big', signed=False)
            if len(self.tcpData) >= messageLen:
                infoMessage = self.datagram_received(self.tcpData[0:messageLen])
                self.tcpData = self.tcpData[messageLen:]
                self.messageComplete = True

                return infoMessage

    # Entete pour toutes les messages
    def entete(self, longueur_message, num_sequence, type):
        longueur = longueur_message + constants.SIZE_ENTETE
        num_sequence = self.value_to_bit(num_sequence, constants.SIZE_NUMERO_SEQUENCE)
        msg_type = self.value_to_bit(type, constants.SIZE_TYPE)

        return longueur, num_sequence, msg_type 

    # Format Type 0 : Acquittement
    def msg_acquittemen(self, num_sequence):
        info = self.entete(0, num_sequence, constants.ACQUITTEMENT)

        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        return struct.pack('>HH', longueur, entete_info)

    # Format Type 1 : Connexion
    def msg_connexion(self, num_sequence, pseudonyme):
        info = self.entete(len(pseudonyme), num_sequence, constants.CONNEXION)
        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        # Package with all the info (all packs to send)
        buffer = struct.pack('>HH', longueur, entete_info)
        buffer += struct.pack(str(len(pseudonyme)) + 's', pseudonyme.encode('utf-8'))

        return buffer

    # Format Type 2 : Quitter Application
    def msg_quitter_app(self, num_sequence):
        info = self.entete(0, num_sequence, constants.QUITTER_APP)

        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        return struct.pack('>HH', longueur, entete_info)

    # Format 3 : Selection du Film
    def msg_selection_film(self, num_sequence, titleFilm):
        info = self.entete(len(titleFilm), num_sequence, constants.SELECTION_FILM)
        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        # Package with all the info (all packs to send)
        buffer = struct.pack('>HH', longueur, entete_info)
        buffer += struct.pack(str(len(titleFilm)) + 's', titleFilm.encode('utf-8'))

        return buffer

    # Format 4 : Quitter salon Film
    def msg_quitter_salon(self, num_sequence):
        info = self.entete(0, num_sequence, constants.QUITTER_FILM)

        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        return struct.pack('>HH', longueur, entete_info)

    # Format Type 5 : Liste des films
    def msg_liste_des_films(self, movies, num_sequence):
        info = self.entete(0, num_sequence, constants.LISTE_FILMS)
        length_total_films = 0
        buffer = None

        for movie in movies:
            length = constants.SIZE_MOVIE_PACK + len(movie.movieTitle)
            length_total_films += length

            ip = movie.movieIpAddress.split(".")
            pack = struct.pack('>BBBBHHB' + str(len(movie.movieTitle)) + 's',
                               int(ip[0]),
                               int(ip[1]),
                               int(ip[2]),
                               int(ip[3]),
                               movie.moviePort,
                               length,
                               movie.movieId,
                               str(movie.movieTitle).encode('utf-8'))
            if buffer is None:
                buffer = pack
            else:
                buffer += pack

        longueur = info[0] + length_total_films
        entete_info = int(info[1] + info[2], 2)

        # Insert the entete in the firsts bytes of the final package
        return struct.pack('>HH', longueur, entete_info) + buffer

    # Format Type 6 : Liste des utilisateurs
    def msg_liste_des_utilisateurs(self, utilisateurs, server, num_sequence):
        info = self.entete(0, num_sequence, constants.LISTE_UTILISATEURS)
        buffer = None
        length_total_utilisateurs = 0

        for utilisateur in utilisateurs:
            length = 1 + 1 + len(utilisateur.userName)
            length_total_utilisateurs += length
            pseudo = utilisateur.userName

            # Main room -> Status 0
            if utilisateur.userChatRoom == c2w_constants.ROOM_IDS.MAIN_ROOM:
                status = 0
            # Movie room -> Status Movie Id
            else:
                status = server.getMovieByTitle(utilisateur.userChatRoom).movieId

            pack = struct.pack('>BB' + str(len(pseudo)) + 's',
                                          len(pseudo),
                                          status,
                                          pseudo.encode('utf-8'))

            if buffer is None:
                buffer = pack
            else:
                buffer += pack

        longueur = info[0] + length_total_utilisateurs
        entete_info = int(info[1] + info[2], 2)

        # Insert the entete in the firsts bytes of the final package
        return struct.pack('>HH', longueur, entete_info) + buffer

    # Format Type 7 : Acceptation connexion
    def msg_acceptation_connexion(self, num_sequence):
        info = self.entete(0, num_sequence, constants.ACCEPTATION_UTILISATEUR)

        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        return struct.pack('>HH', longueur, entete_info)

    # Format Type 8 : Refus de connexion
    def msg_refus_connexion(self, num_sequence):
        info = self.entete(0, num_sequence, constants.REFUS_CONNEXION)

        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        return struct.pack('>HH', longueur, entete_info)

    # Format Type 9 : Chat
    def msg_chat(self, num_sequence, pseudo, message):
        info = self.entete(len(pseudo) + len(message) + 1, num_sequence, constants.CHAT)
        longueur = info[0]
        entete_info = int(info[1] + info[2], 2)

        buffer = struct.pack('>B' + str(len(pseudo)) + 's' + str(len(message)) + 's',
                           len(pseudo), pseudo.encode('utf-8'), message.encode('utf-8'))

        # Insert the entete in the firsts bytes of the final package
        return struct.pack('>HH', longueur, entete_info) + buffer

    # Unpack movie list
    def get_movie_list(self, data):
        i = 0
        infoMovies = []

        while i < len(data):
            firstData = struct.unpack('>BBBBHH', data[i:i+8])
            ip = str(firstData[0]) + '.' + str(firstData[1]) + '.' + str(firstData[2]) + '.' + str(firstData[3])
            port = firstData[4]
            length = firstData[5]
            lenMovieTitle = firstData[5] - constants.SIZE_MOVIE_PACK

            movieData = struct.unpack('>BBBBHHB' + str(lenMovieTitle) + 's', data[i:i + length])
            movieName = movieData[7].decode('utf-8')

            infoMovies.append((movieName, ip, port))
            i += firstData[5]

        return infoMovies

    # Unpack user list
    def get_user_list(self, data):
        i = 0
        infoUsers = []

        while i < len(data):
            firstData = struct.unpack('>BB', data[i:i + 2])
            pseudoLen = firstData[0]

            if firstData[1] == 0:
                status = c2w_constants.ROOM_IDS.MAIN_ROOM
            else:
                status = c2w_constants.ROOM_IDS.MOVIE_ROOM

            userData = struct.unpack('>BB' + str(pseudoLen) + 's', data[i:i + 2 + pseudoLen])
            userName = userData[2].decode('utf-8')

            infoUsers.append((userName, status))
            i += pseudoLen + 2

        return infoUsers
