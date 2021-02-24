#!/usr/bin/python

import socket
import sys

def main(argv):
	# set port number
	# default is 32341 if no input argument
	port_number = 32341
	if len(sys.argv) == 2:
		port_number = int(sys.argv[1])

	# create socket and bind
	sockfd = socket.socket()
	try:
		sockfd.bind(("", port_number))
	except socket.error as err:
		print("Socket bind error: ", err)
		sys.exit(1)


	# listen and accept new connection
	sockfd.listen(5)
	try:
		new, who = sockfd.accept() # Return the TCP connection
	except socket.error as err:
		print("Socket accept error: ", err)
		sys.exit(1)
	
	# print out peer socket address information
	print("Peer socket address information : ", who)

	# receive file name, file size; and create the file
	try:
		data = new.recv(100)
	except socket.error as err:
		print("Recv error: ", err)
		sys.exit(1)
	if data == b'':
		print("Connection is broken")
		sys.exit(1)

	file_name, file_size = data.split(b':')
	
	try:
		f = open(file_name, "wb")
	except OSError as err:
		print("File open error: ", err)
		sys.exit(1)
	temp_filesize = int(file_size)

	# send acknowledge - e.g., "OK"
	new.send(b"OK")

	# receive the file contents
	print("Start receiving . . .")
	while (temp_filesize > 0):
		message = new.recv(1000)
		length_m = len(message)
		if message == b"":
			print("Connection is broken")
			sys.exit(1)
		f.write(message)
		temp_filesize = temp_filesize - length_m 

	# close connection
	print("[Completed]")
	sockfd.close()
	new.close()
	f.close()


if __name__ == '__main__':
	if len(sys.argv) > 2:
		print("Usage: FTserver [<Server_port>]")
		sys.exit(1)
	main(sys.argv)