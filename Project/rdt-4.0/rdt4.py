#!/usr/bin/python3
"""Implementation of RDT4.0

functions: rdt_network_init, rdt_socket(), rdt_bind(), rdt_peer()
           rdt_send(), rdt_recv(), rdt_close()

Student name: Utsav Raj
Date and version: 27/04/2021 ver 1 
Development platform: MacOS
Python version: 3.8.8 64-bit
"""

import socket
import random

# --- other imports --- #
import struct
import select
import math
# --------------------- #


#some constants
PAYLOAD = 1000		#size of data payload of each packet
CPORT = 100			#Client port number - Change to your port number
SPORT = 200			#Server port number - Change to your port number
TIMEOUT = 0.05		#retransmission timeout duration
TWAIT = 10*TIMEOUT 	#TimeWait duration

#store peer address info
__peeraddr = ()		#set by rdt_peer()
#define the error rates and window size
__LOSS_RATE = 0.0	#set by rdt_network_init()
__ERR_RATE = 0.0
__W = 1

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
		#Simulate packet loss
		drop = random.random()
		if drop < __LOSS_RATE:
			#simulate packet loss of unreliable send
			print("WARNING: udt_send: Packet lost in unreliable layer!!")
			return len(byte_msg)

		#Simulate packet corruption
		corrupt = random.random()
		if corrupt < __ERR_RATE:
			err_bytearr = bytearray(byte_msg)
			pos = random.randint(0,len(byte_msg)-1)
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
	length = len(byte_msg)	#length of the byte message object
	i = 0
	while length > 1:
		total += ((byte_msg[i+1] << 8) & 0xFF00) + ((byte_msg[i]) & 0xFF)
		i += 2
		length -= 2

	if length > 0:
		total += (byte_msg[i] & 0xFF)

	while (total >> 16) > 0:
		total = (total & 0xFFFF) + (total >> 16)

	total = ~total

	return total & 0xFFFF


#These are the functions used by appliation

def rdt_network_init(drop_rate, err_rate, W):
	"""Application calls this function to set properties of underlying network.

    Input arguments: packet drop probability, packet corruption probability and Window size
	"""
	random.seed()
	global __LOSS_RATE, __ERR_RATE, __W
	__LOSS_RATE = float(drop_rate)
	__ERR_RATE = float(err_rate)
	__W = int(W)
	print("Drop rate:", __LOSS_RATE, "\tError rate:", __ERR_RATE, "\tWindow size:", __W)


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
	size = struct.calcsize(MSG_FORMAT)
	(msg_type, seq_num, recv_checksum, payload_len), payload = struct.unpack(
        MSG_FORMAT, msg[:size]), msg[size:]
	# Byte order conversion otherwise receiving error
	return (msg_type, seq_num, recv_checksum,
            socket.ntohs(payload_len)), payload 

# if the received packet is corrupted - then true.
def check_if_corrupt(recv_pkt):
	(msg_type, seq_num, recv_checksum, payload_len), payload = unpack_msg(
        recv_pkt)
	init_msg = struct.Struct(MSG_FORMAT).pack(msg_type, seq_num, 0,
                                              socket.htons(
                                                  payload_len)) + payload

	calc_checksum = __IntChksum(bytearray(init_msg))
	result = recv_checksum != calc_checksum
	return result

# Check if the received packet is low <= pkt_type <= high
def type_between(recv_pkt, pkt_type, low, high):
	(recv_type, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
	if recv_seq_num < low:  # Case -- Modular arithmetic
		recv_seq_num += SEQ_SIZE
	return recv_type == pkt_type and low <= recv_seq_num <= high

# TRUE if the received packet is pkt_type
def is_type(recv_pkt, pkt_type):
	(recv_type, _, _, _), _ = unpack_msg(recv_pkt)
	return recv_type == pkt_type

# Create the ACK 
def create_ACK(seq_num):
    # Make initial message
	msg_format = struct.Struct(MSG_FORMAT)
	checksum = 0  # First set checksum to 0
	init_msg = msg_format.pack(ACK_ID, seq_num, checksum,
                               socket.htons(0)) + b''
    # checksum calculation
	checksum = __IntChksum(bytearray(init_msg))
    # Complete msg
	return msg_format.pack(ACK_ID, seq_num, checksum, socket.htons(0)) + b''


def __checker(msg):
	if check_if_corrupt(msg):
		(msg_type, _, _, payload_len), payload = unpack_msg(msg)
		if msg_type == ACK_ID:
			return "Recieved a corrupt package: Type = ACK, Length = " + str(HEADER_SIZE)
		elif msg_type == DATA_ID:
			return "Recieved a corrupt package: Type = DATA, Length = " + str(payload_len + HEADER_SIZE)
		else:
			return "Corrupted message type ID - ACK or DATA"
	msg_str = ""
	(msg_type, seq_num, checksum, payload_len), payload = unpack_msg(msg)
	if msg_type == ACK_ID:
		msg_str += "the ACK"
	elif msg_type == DATA_ID:
		msg_str += "the DATA"
	msg_str += " with the seqNo. : %d" % seq_num
	return msg_str


# -- other constants -- #
DATA_ID = 12  # ID 12 for Data
ACK_ID = 11  # ID 11 means ACK
HEADER_SIZE = 6  # Header size is 6 bytes as mentioned
MSG_FORMAT = 'BBHH'  # Header structure
SEQ_SIZE = 256  # Sequence number from 0 to 255 (256 in total)

next_seq_num = 0  # Next sequence number of sender (initially set to 0)
exp_seq_num = 0  # Expected sequence number of receiver (initially set to 0)
__S = 0  # base -- Sender 
__N = 1  # Number of packets to be sent
data_buffer = []  
# --------------------- #


def rdt_send(sockd, byte_msg):
	"""Application calls this function to transmit a message (up to
	W * PAYLOAD bytes) to the remote peer through the RDT socket.

	Input arguments: RDT socket object and the message bytes object
	Return  -> size of data sent on success, -1 on error

	Note: (1) This function will return only when it knows that the
	whole message has been successfully delivered to remote process.
	(2) Catch any known error and report to the user.
	"""
	######## Your implementation #######
	global __S, next_seq_num, __N, data_buffer
	whole_msg_len = len(byte_msg)  # Size of the whole message, to be returned

    # Number of packets needed to send the whole message (byte_msg)
	__N = int(math.ceil(
        float(len(byte_msg)) / PAYLOAD))  # float() to prevent less number of package

	snd_pkt = [None] * __N  # Packets to be sent
	first_unacked_ind = 0  # Index of the 1st unACK packet
	__S = next_seq_num  # Update the baase -- sender

	print("rdt_send: Send %d packets" % __N)

    # Create and send all the data packets
	for i in range(__N):
		# Cut and extract message remaining
		if len(byte_msg) > PAYLOAD:
			data = byte_msg[0:PAYLOAD]
			byte_msg = byte_msg[PAYLOAD:]
		else:
			data = byte_msg
			byte_msg = None

   		# Make the data packet
		msg_format = struct.Struct(MSG_FORMAT)
		checksum = 0  # First set checksum to 0
		init_msg = msg_format.pack(DATA_ID, next_seq_num, checksum,
                               socket.htons(len(data))) + data

    	# Calculate checksum
		checksum = __IntChksum(bytearray(init_msg))

		# Complete msg
		snd_pkt[i] = msg_format.pack(DATA_ID, next_seq_num, checksum,
                                   socket.htons(len(data))) + data

        # Send the new packet
		try:
			__udt_send(sockd, __peeraddr, snd_pkt[i])
		except socket.error as err_msg:
			print("send: Socket send error: ", err_msg)
			return -1
		print("rdt_send: Sent " + __checker(snd_pkt[i]))

        # Increase the sequence number
		next_seq_num = (next_seq_num + 1) % SEQ_SIZE

	r_sock_list = [sockd]  
	while True:  # While all ACKs not received 
        # Wait for timeout or the ACK
		r, _, _ = select.select(r_sock_list, [], [], TIMEOUT)
		if r:  # ACK r DATA just reached
			for sock in r:
                # Try to receive ACK or DATA
				try:
                    # Include header
					recv_pkt = __udt_recv(sock, PAYLOAD + HEADER_SIZE)
				except socket.error as err_msg:
					print("__udt_recv error: ", err_msg)
					return -1
				
                # If corrupted, Ignore
				if check_if_corrupt(recv_pkt):
					print("rdt_send: " +  __checker(recv_pkt))
                # If is not corrupted,  ACK
				elif is_type(recv_pkt, ACK_ID):
                    # IF out-of-range, Ignore
					if not type_between(recv_pkt, ACK_ID, __S,
                                             __S + __N - 1):
						print("rdt_send: received out-of-range ACK")
                    # ELSE, accept and set ACK status.
					elif type_between(recv_pkt, ACK_ID, __S,
                                           __S + __N - 2):
						print("rdt_send: All segments %d to %d are acknowledged" % (
                            __S, __S + __N - 2))
						(_, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
                        # Update the first unACK index (as it is cumulative ACK)
						first_unacked_ind = max( (recv_seq_num - __S + SEQ_SIZE) % SEQ_SIZE + 1,
                            first_unacked_ind)
                    # Last and final ACK and return
					elif type_between(recv_pkt, ACK_ID, __S + __N - 1,
                                           __S + __N - 1):
						return whole_msg_len  
                # If is a not corrupt DATA
				elif is_type(recv_pkt, DATA_ID):
					print("rdt_send: Not Received " + __checker(recv_pkt))
                    # If expected, buffer and ACK
					(_, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
					if (recv_seq_num == exp_seq_num):
						print("rdt_send: Expected (%d)" % exp_seq_num)
                        # If not in buffer, add the msg to buffer
						if recv_pkt not in data_buffer:
							data_buffer.append(recv_pkt)
                        # ACK the expected DATA
						try:
							__udt_send(sockd, __peeraddr,
                                       create_ACK(exp_seq_num))
						except socket.error as err_msg:
							print("rdt_send: Error in sending ACK to received "
                                  "data: " + str(
                                    err_msg))
							return -1
						print("rdt_send: Sent ACK[%d]" % exp_seq_num)
                    # If DATA not expected, send ACK to expected - 1 (older)
					else:
                        # Send ACK for the previous to the expected
						try:
							__udt_send(sockd, __peeraddr, create_ACK(
                                ((exp_seq_num - 1 + SEQ_SIZE) % SEQ_SIZE)))
						except socket.error as err_msg:
							print("send(): Error in ACK-ing expected data: " +
                                  str(err_msg))
							return b''
						print(
                            "rdt_send: NOT expected (%d) , sent ACK["
                            "%d]" % (
                                exp_seq_num,
                                (exp_seq_num - 1 + SEQ_SIZE) % SEQ_SIZE))
        # Timeout and re-transmitting the packet
		else:
			for i in range(first_unacked_ind, __N):
				try:
					__udt_send(sockd, __peeraddr, snd_pkt[i])
					print("rdt_send: TIMEOUT!! Retransmit " + (__checker(snd_pkt[i]))+ " again" )
				except socket.error as err_msg:
					print("Socket send error: ", err_msg)
					return -1



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
	######## Your implementation #######
	global exp_seq_num, data_buffer

    # Check if buffer
	while len(data_buffer) > 0:
        # FIFO manner Pop 
		recv_pkt = data_buffer.pop(0)  # NOT corrupted as buffer

        # Buffered data with expected seq num, accept and return
		(_, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
		if (recv_seq_num == exp_seq_num):
			print("rdt_recv: Expected (%d)" % exp_seq_num)
            # Increase expected sequence number
			exp_seq_num = (exp_seq_num + 1) % SEQ_SIZE
			(_), payload = unpack_msg(recv_pkt)  # Extract payload
			return payload

	while True:  # Repeat until received the expected DATA
		try:
			recv_pkt = __udt_recv(sockd, length + HEADER_SIZE)
		except socket.error as err_msg:
			print("rdt_recv: Socket receive error: " + str(err_msg))
			return b''
		print("rdt_recv: " + __checker(recv_pkt))

        # If packet is corrupt or is ACK, Ignore
		if check_if_corrupt(recv_pkt) or is_type(recv_pkt, ACK_ID):
			print("rdt_recv: Received corrupted or ACK")

        # If received DATA
		elif is_type(recv_pkt, DATA_ID):
            # If DATA has expected seq num, accept
			(_, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
			if (recv_seq_num == exp_seq_num):
                # Send ACK for this expected packet
				try:
					 __udt_send(sockd, __peeraddr, create_ACK(exp_seq_num))
				except socket.error as err_msg:
					print("recv(): Error in ACK-ing expected data: " + str(
                        err_msg))
					return b''
				print("rdt_recv: Expected, sent ACK seqNo. %d" % exp_seq_num)
                # Increment expected sequence number
				exp_seq_num = (exp_seq_num + 1) % SEQ_SIZE
				(_), payload = unpack_msg(recv_pkt)  # Extract payload
				return payload
            # If DATA is not expected DATA
			else:
                # Send ACK for the previous expected DATA
				try:
					__udt_send(sockd, __peeraddr,
                               create_ACK((exp_seq_num - 1 + SEQ_SIZE) % SEQ_SIZE))
				except socket.error as err_msg:
					print("rdt_recv: Error in ACK-ing expected data: " + str(
                        err_msg))
					return b''
				print("rdt_recv: NOT expected (%d) (expected : %d )" % (
                    exp_seq_num, (exp_seq_num - 1 + SEQ_SIZE) % SEQ_SIZE))


def rdt_close(sockd):
	"""Application calls this function to close the RDT socket.

	Input argument: RDT socket object

	Note: (1) Catch any known error and report to the user.
	(2) Before closing the RDT socket, the reliable layer needs to wait for TWAIT
	time units before closing the socket.
	"""
	######## Your implementation #######
	r_sock_list = [sockd]  # Used in select.select()

	can_close = False 

	while not can_close:
		r, _, _ = select.select(r_sock_list, [], [],
                                TWAIT)  # Wait for TWAIT time
		if r:  # If any activity
			for sock in r:
                # Try to receive 
				try:
					recv_pkt = __udt_recv(sock, PAYLOAD + HEADER_SIZE)
				except socket.error as e:
					print("Socket recv error: ", e)
				print("rdt_recv: Received a message of size " + __checker(recv_pkt) )

				# Not corrupted
				if not check_if_corrupt(recv_pkt):
                    # Ack the DATA packet
					(_, recv_seq_num, _, _), _ = unpack_msg(recv_pkt)
					try:
						length = __udt_send(sockd, __peeraddr, create_ACK(recv_seq_num))
					except socket.error as err_msg:
						print("close(): Error in ACK-ing data: " + str(
                            err_msg))
					print("rdt_send: Sent last ACK message of size %d" % length)
		# Timeout
		else:  
			can_close = True
			try:
				print("rdt_close: Nothing happened for 0.500 second")
				# Close socket
				sockd.close()
				print("rdt_close: Release the socket")
			except socket.error as err_msg:
				print("Socket close error: ", err_msg)
