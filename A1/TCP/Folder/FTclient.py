#!/usr/bin/python

import socket
import os.path
import sys

def main(argv):

	# open the target file; get file size
	try:
		file_size = os.path.getsize(argv[3])
	except os.error as err:
		print("File error: ", err)
		sys.exit(1)

	target_file = open(argv[3], "rb")

	# create socket and connect to server
	try:
		sockfd = socket.socket()
		sockfd.connect((argv[1], int(argv[2])))
	except socket.error as err:
		print("Socket error: ", err)
		sys.exit(1)

	# once the connection is set up; print out 
	# the socket address of your local socket
	print("The socket address is: " , sockfd.getsockname())

	# send file name and file size as one string separate by ':'
	# e.g., socketprogramming.pdf:435678
	message = argv[3]+ ":" + str(file_size)
	sockfd.send(message.encode('ascii'))

	# receive acknowledge - e.g., "OK"
	r_msg = sockfd.recv(50)

	if r_msg != b"OK":
		print("Negative acknowledgment received")
		sys.exit(1)

	# send the file contents
	print("Start sending ...")
	temp_filesize = file_size
	block_size = 1000
	while (temp_filesize > 0) :
		data = target_file.read(block_size)
		length_data = len(data)
		if length_data == 0:
			sys.exit(1)
		try:
			sockfd.sendall(data)
		except socket.error as err:
			print("Sendall error: ", err)
			sys.exit(1)
		temp_filesize = temp_filesize - length_data

	# close connection
	print("[Completed]")
	sockfd.close()


if __name__ == '__main__':
	if len(sys.argv) != 4:
		print("Usage: FTclient.py <Server_addr> <Server_port> <filename>")
		sys.exit(1)
	main(sys.argv)