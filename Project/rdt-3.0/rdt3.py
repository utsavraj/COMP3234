#!/usr/bin/python3
"""Implementation of RDT3.0

functions: rdt_network_init(), rdt_socket(), rdt_bind(), rdt_peer()
           rdt_send(), rdt_recv(), rdt_close()

Student name: Utsav Raj
Date and version: 05/04/2021 ver 1 
Development platform: MacOS
Python version: 3.8.8 64-bit
"""

import socket
import random

# --- other imports --- #
import struct
import select
# --------------------- #


#some constants
PAYLOAD = 1000		#size of data payload of the RDT layer
CPORT = 100			#Client port number - Change to your port number
SPORT = 200			#Server port number - Change to your port number
TIMEOUT = 0.05		#retransmission timeout duration
TWAIT = 10*TIMEOUT 	#TimeWait duration

#store peer address info
__peeraddr = ()		#set by rdt_peer()
#define the error rates
__LOSS_RATE = 0.0	#set by rdt_network_init()
__ERR_RATE = 0.0



#internal functions - being called within the module
def __udt_send(sockd, peer_addr, byte_msg):
    """This function is for simulating packet loss or corruption in an unreliable channel.

    Input arguments: Unix socket object, peer address 2-tuple and the message
    Return  -> size of data sent, -1 on error
    Note: it does not catch any exception
    """
    global __LOSS_RATE, __ERR_RATE
    if peer_addr == ():
        print("Socket send error: Peer address not set yet")
        return -1
    else:
        # Simulate packet loss
        drop = random.random()
        if drop < __LOSS_RATE:
            # simulate packet loss of unreliable send
            print("WARNING: udt_send: Packet lost in unreliable layer!!")
            return len(byte_msg)

        # Simulate packet corruption
        corrupt = random.random()
        if corrupt < __ERR_RATE:
            err_bytearr = bytearray(byte_msg)
            pos = random.randint(0, len(byte_msg) - 1)
            val = err_bytearr[pos]
            if val > 1:
                err_bytearr[pos] -= 2
            else:
                err_bytearr[pos] = 254
            err_msg = bytes(err_bytearr)
            print("WARNING: udt_send: Packet corrupted in unreliable layer!!")
            return sockd.sendto(err_msg, peer_addr)
        else:
            return sockd.sendto(byte_msg, peer_addr)


def __udt_recv(sockd, length):
    """Retrieve message from underlying layer

    Input arguments: Unix socket object and the max amount of data to be received
    Return  -> the received bytes message object
    Note: it does not catch any exception
    """
    (rmsg, peer) = sockd.recvfrom(length)
    return rmsg


def __IntChksum(byte_msg):
    """Implement the Internet Checksum algorithm

    Input argument: the bytes message object
    Return  -> 16-bit checksum value
    Note: it does not check whether the input object is a bytes object
    """
    total = 0
    length = len(byte_msg)  #length of the byte message object
    i = 0
    while length > 1:
        total += ((byte_msg[i + 1] << 8) & 0xFF00) + ((byte_msg[i]) & 0xFF)
        i += 2
        length -= 2

    if length > 0:
        total += (byte_msg[i] & 0xFF)

    while (total >> 16) > 0:
        total = (total & 0xFFFF) + (total >> 16)

    total = ~total

    return total & 0xFFFF


#These are the functions used by application

def rdt_network_init(drop_rate, err_rate):
    """Application calls this function to set properties of underlying network.

    Input arguments: packet drop probability and packet corruption probability
    """
    random.seed()
    global __LOSS_RATE, __ERR_RATE
    __LOSS_RATE = float(drop_rate)
    __ERR_RATE = float(err_rate)
    print("Drop rate:", __LOSS_RATE, "\tError rate:", __ERR_RATE)


def rdt_socket():
    """Application calls this function to create the RDT socket.

    Null input.
    Return the Unix socket object on success, None on error

    Note: Catch any known error and report to the user.
    """
    ######## Your implementation #######
    ### Taken from rdt1.py ###
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.error as err_msg:
        print("Socket creation error: ", err_msg)
        return None
    return sock


def rdt_bind(sockd, port):
    """Application calls this function to specify the port number
    used by itself and assigns them to the RDT socket.

    Input arguments: RDT socket object and port number
    Return	-> 0 on success, -1 on error

    Note: Catch any known error and report to the user.
    """
    ######## Your implementation #######
    ### Taken from rdt1.py ###
    try:
        sockd.bind(("", port))
    except socket.error as err_msg:
        print("Socket bind error: ", err_msg)
        return -1
    return 0


def rdt_peer(peer_ip, port):
    """Application calls this function to specify the IP address
    and port number used by remote peer process.

    Input arguments: peer's IP address and port number
    """
    ######## Your implementation #######
    ### Taken from rdt1.py ###
    global __peeraddr
    __peeraddr = (peer_ip, port)

# Upnpck function for data packets
def unpack_msg(msg):
    size = struct.calcsize('BBHH')
    (msg_type, seq_num, recv_checksum, payload_len), payload = struct.unpack('BBHH', msg[:size]), msg[size:]
	# Byte order conversion otherwise receiving error
    return (msg_type, seq_num, recv_checksum, socket.ntohs(payload_len)), payload  

# if the received packet is corrupted - then true.
def check_if_corrupt(recv_pkt):
    (msg_type, seq_num, recv_checksum, payload_len), payload = unpack_msg(recv_pkt)
    init_msg = struct.Struct('BBHH').pack(msg_type, seq_num, 0, socket.htons(payload_len)) + payload
    calc_checksum = __IntChksum(bytearray(init_msg))
    corrupted = recv_checksum != calc_checksum
    return corrupted


# -- other constants -- #
ACK_ID = 11  # ID 11 means ACK
DATA_ID = 12  # ID 12 means Data
HEADER_SIZE = 6  # Header size is 6 bytes as mentioned

# Last ACK number
last_ack_num = None

# state number for send, recieve
send_state = 0
rcv_state = 0

# Data buffer
data_buffer = []
# --------------------- #

def rdt_send(sockd, byte_msg):
    """Application calls this function to transmit a message to
    the remote peer through the RDT socket.

    Input arguments: RDT socket object and the message bytes object
    Return  -> size of data sent on success, -1 on error

    Note: Make sure the data sent is not longer than the maximum PAYLOAD
    length. Catch any known error and report to the user.
    """
    global PAYLOAD, __peeraddr, data_buffer, HEADER_SIZE, send_state, last_ack_num, ACK_ID

    # Make sure message is not greater than payload
    msg = ""
    if len(byte_msg) > PAYLOAD:
        msg = byte_msg[0:PAYLOAD]
    else:
        msg = byte_msg

    # Make data packet 0
	# Make initial message
    msg_format = struct.Struct('BBHH')
    checksum = 0  
    init_msg = msg_format.pack(DATA_ID, send_state, checksum, socket.htons(len(msg))) + msg
    # Calculate checksum
    checksum = __IntChksum(bytearray(init_msg))
    # Message with checksum
    snd_pkt = msg_format.pack(DATA_ID, send_state, checksum, socket.htons(len(msg))) + msg

    # Send packet
    try:
        sent_len = __udt_send(sockd, __peeraddr, snd_pkt)
    except socket.error as err_msg:
        print("Socket send error: ", err_msg)
        return -1
    print("rdt_send: Sent one message of size %d" % sent_len)

    r_sock_list = [sockd] 
    recv_expected = False 

 	# While not received the expected ACK
    while not recv_expected: 
        # Wait for the expected ACK or get timeout
        r, _, _ = select.select(r_sock_list, [], [], TIMEOUT)
        if r:  # if DATA or ACK came
            for sock in r:
                # Receive DATA or ACK
                try:
                    recv_msg = __udt_recv(sock, PAYLOAD + HEADER_SIZE)  
                    (msg_type, recv_seq_num, _, _), _ = unpack_msg(recv_msg)
                except socket.error as err_msg:
                    print("Socket send error: ", err_msg)
                    return -1
                # Corrupted or unexpected ACK, wait
                if check_if_corrupt(recv_msg):
                    print("rdt_send: Recieved a corrupted packet: Type = ACK, Length = %d" % len(recv_msg))
                elif msg_type == ACK_ID and recv_seq_num == 1 - send_state :
                    print("rdt_send: Recieved a corrupted packet: Type = ACK, Length = %d" % len(recv_msg))
                # Otherwise, receive expected ACK
                elif(msg_type == ACK_ID and recv_seq_num == send_state):
                    print("rdt_send: Recieved the expected ACK %d" % send_state)
                    send_state ^= 1  # sequence number is switched
                    return sent_len - HEADER_SIZE  # Return size of the payload data sent
                # Received the whole DATA while waiting for ACK
                else:
                    if recv_msg not in data_buffer:  # add msg to buffer if not already present
                        data_buffer.append(recv_msg)
                    # Try to ACK the received DATA
                    (_, data_seq_num, _, _), _ = unpack_msg(recv_msg)
                    try:
                        __udt_send(sockd, __peeraddr, create_ack(data_seq_num))
                    except socket.error as err_msg:
                        print("Socket send error: " + err_msg)
                        return -1
                    # Update last ACK-ed number
                    last_ack_num = data_seq_num
                    print("rdt_send: ACK %d" % data_seq_num)
		# Timeout and re-transmitting the packet
        else:  
            try:
                sent_len = __udt_send(sockd, __peeraddr, snd_pkt)
            except socket.error as err_msg:
                print("Socket send error: ", err_msg)
                return -1
            (_), payload = unpack_msg(snd_pkt)
            print("rdt_send: TIMEOUT!! Retransmit the packet %d again" % (send_state))

# Create the ACK 
def create_ack(seq_num):
    global ACK_ID
    msg_format = struct.Struct('BBHH')
    checksum = 0 
    init_msg = msg_format.pack(ACK_ID, seq_num, checksum, socket.htons(0)) + b''
    checksum = __IntChksum(bytearray(init_msg))
    # CComplete packet
    return msg_format.pack(ACK_ID, seq_num, checksum, socket.htons(0)) + b''


def rdt_recv(sockd, length):
    """Application calls this function to wait for a message from the
    remote peer; the caller will be blocked waiting for the arrival of
    the message. Upon receiving a message from the underlying UDT layer,
    the function returns immediately.

    Input arguments: RDT socket object and the size of the message to
    received.
    Return  -> the received bytes message object on success, b'' on error

    Note: Catch any known error and report to the user.
    """
    global __peeraddr, data_buffer, rcv_state, HEADER_SIZE, last_ack_num, ACK_ID, DATA_ID

    # Check to see if anything in the buffer
    while len(data_buffer) > 0:
        # Get the data which came first first.
        recv_pkt = data_buffer.pop(0) 
        (msg_type, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
        if recv_seq_num == rcv_state:  # Buffer data has expected sequence num, accept
            print("rdt_recv: Received expected package of size %d" % (len(recv_pkt)))
            rcv_state ^= 1  # sequence num flipped to move onto next packet
            return unpack_msg(recv_pkt)[1]

    recv_expected_data = False
    while not recv_expected_data:  # Repeat until received expected DATA
        try:
            recv_pkt = __udt_recv(sockd, length + HEADER_SIZE)
            (msg_type, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
        except socket.error as err_msg:
            print("Socket recv error: " + str(err_msg))
            return b''

        # If packet is corrupt or wrong seq num, send the previous ACK
        if check_if_corrupt(recv_pkt) or recv_seq_num == 1-rcv_state:
            if (msg_type == ACK_ID):
                print("rdt_rcv: Recieved a corrupted packet: Type = ACK, Length = %d" % len(recv_pkt))
            elif (msg_type == DATA_ID):
                print("rdt_rcv: Recieved a corrupted packet: Type = DATA, Length = %d" % len(recv_pkt))

            snd_ack = create_ack(1-rcv_state) # previous ACK
            try:
                __udt_send(sockd, __peeraddr, snd_ack)
            except socket.error as err_msg:
                print("Socket send error: " + str(err_msg))
                return b''
            last_ack_num = 1-rcv_state  # Update the last ACK-ed number
            print("rdt_recv: Sent old ACK %d" % (1-rcv_state))
        # If received DATA with the needed seq num, send ACK
        elif recv_seq_num == rcv_state:
            (_), payload = unpack_msg(recv_pkt)  # Extract payload
            print("rdt_recv: Received message of size %d" % (len(recv_pkt)))
            try:
                __udt_send(sockd, __peeraddr, create_ack(rcv_state))
            except socket.error as err_msg:
                print("Socket send error: " + str(err_msg))
                return b''
            print("rdt_recv: Sent expected ACK %d" % rcv_state)
            last_ack_num = rcv_state  # keep last ACK number
            rcv_state ^= 1 
            return payload


def rdt_close(sockd):
    """Application calls this function to close the RDT socket.

    Input argument: RDT socket object

    Note: (1) Catch any known error and report to the user.
    (2) Before closing the RDT socket, the reliable layer needs to wait for TWAIT
    time units before closing the socket.
    """
    global last_ack_num, DATA_ID

    r_sock_list = [sockd] 

    can_close = False  

    while not can_close:
        r, _, _ = select.select(r_sock_list, [], [], TWAIT)  # Wait for TWAIT time
        if r:  # In-coming packet
            for sock in r:
                try:
                    recv_pkt = __udt_recv(sock, PAYLOAD + HEADER_SIZE)  
                    (pkt_type, pkt_seq, _, _), _ = unpack_msg(recv_pkt)
                except socket.error as e:
                    print("Socket recv error: ", e)
                print("rdt_recv: Received a message of size %d" % len(recv_pkt))
                # If not corrupt and the DATA is the last_ack_num
                if not check_if_corrupt(recv_pkt) and pkt_type == DATA_ID and pkt_seq == last_ack_num:
                    # ACK the DATA packet
                    try:
                        length = __udt_send(sockd, __peeraddr, create_ack(last_ack_num))
                    except socket.error as e:
                        print("Socket send error: " + str(e))
                    print("rdt_send: Sent last ACK message of size %d" % length)
        else:  
            can_close = True
            # Close socket
            try:
                print("rdt_close: Nothing happened for 0.500 second")
                sockd.close()
                print("rdt_close: Release the socket")
            except socket.error as e:
                print("Socket close error: ", e)