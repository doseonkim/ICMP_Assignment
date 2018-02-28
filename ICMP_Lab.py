from socket import *
import os
import sys
import struct
import time
import select
import binascii

ICMP_ECHO_REQUEST = 8

error_message = ["Net Unreachable", "Host Unreachable", "Protocol Unreachable", "Port Unreachable", "Fragmentation Needed and Don't Fragment was Set",
"Source Route Failed", "Destination Network Unknown", "Destination Host Unknown", "Source Host Isolated", "Communication with Destination Network is Administratively Prohibited", 
"Communication with Destination Host is Administratively Prohibited", "Destination Network Unreachable for Type of Service", "Destination Host Unreachable for Type of Service", 
"Communication Administratively Prohibited", "Host Precedence Violation", "Precedence cutoff in effect"]
rtt_data = []
sent_count = 0
recv_count = 0

def checksum(string):
	csum = 0
	countTo = (len(string) // 2) * 2
	count = 0
	while count < countTo:
		thisVal = ord(string[count+1]) * 256 + ord(string[count])
		csum = csum + thisVal
		csum = csum & 0xffffffff
		count = count + 2
		
	if countTo < len(string):
		csum = csum + ord(string[len(string) - 1])
		csum = csum & 0xffffffff
		
	csum = (csum >> 16) + (csum & 0xffff)
	csum = csum + (csum >> 16)
	answer = ~csum
	answer = answer & 0xffff
	answer = answer >> 8 | (answer << 8 & 0xff00)
	return answer


def receiveOnePing(mySocket, ID, timeout, destAddr):
	global recv_count, rtt_data, error_message
	
	timeLeft = timeout
	while 1:
		startedSelect = time.time()
		whatReady = select.select([mySocket], [], [], timeLeft)
		howLongInSelect = (time.time() - startedSelect)
		if whatReady[0] == []: # Timeout
			return "Request timed out."
			
		timeReceived = time.time()
		recPacket, addr = mySocket.recvfrom(1024)
		
		#Fill in start
		#Fetch the ICMP header from the IP packet
		header = recPacket[20:28]
		
		#use python unpack to get appropriate values from header.
		type, code, checksum, id, sequence = struct.unpack('bbHHh',header)
		#Debug to see what received back.
		#print("type: ", type)
		#print("code: ", code)
		#print("checksum: ", checksum)
		#print("id: ", id)
		#print("sequence: ", sequence)
		
		#compare ID to the one we sent from our os.getpid();
		#make sure it is an Echo reply using type 0 and code 0.
		if ID == id and type == 0 and code == 0:
			#Time sent as data. data comes after header so [28 + 8] length unpack.
			sent_time = struct.unpack("d", recPacket[28:36])[0]
			rtt_time = (timeReceived - sent_time)
			rtt_data.append(rtt_time)
			recv_count += 1
			return rtt_time #time sent - time received. 
		elif ID == id and type == 3: #unable to test the error
			return error_message[code]
			
		#Fill in end
		
		timeLeft = timeLeft - howLongInSelect
		if timeLeft <= 0:
			return "Request timed out."

def sendOnePing(mySocket, destAddr, ID):
	
	global sent_count
	
	# Header is type (8), code (8), checksum (16), id (16), sequence (16)
	
	myChecksum = 0
	# Make a dummy header with a 0 checksum
	# struct -- Interpret strings as packed binary data
	header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
	data = struct.pack("d", time.time())
	#debug_time = time.time();
	# Calculate the checksum on the data and the dummy header.
	myChecksum = checksum(str(header + data))
	
	# Get the right checksum, and put in the header
	if sys.platform == 'darwin':
		# Convert 16-bit integers from host to network byte order
		myChecksum = htons(myChecksum) & 0xffff
	else:
		myChecksum = htons(myChecksum)
		
	header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
	packet = header + data
	
	#Debug to see ICMP request sent.
	#print("SENT TIME SEND: ", debug_time);
	
	mySocket.sendto(packet, (destAddr, 1)) # AF_INET address must be tuple, not str
	# Both LISTS and TUPLES consist of a number of objects
	# which can be referenced by their position number within the object.
	sent_count += 1


def doOnePing(destAddr, timeout):
	icmp = getprotobyname("icmp")
	# SOCK_RAW is a powerful socket type. For more details: http://sockraw.org/papers/sock_raw
	
	mySocket = socket(AF_INET, SOCK_RAW, icmp)
	
	myID = os.getpid() & 0xFFFF # Return the current process i
	sendOnePing(mySocket, destAddr, myID)
	delay = receiveOnePing(mySocket, myID, timeout, destAddr)
	mySocket.close()
	return delay

def ping(host, timeout=1):
	global sent_count, recv_count, rtt_data
	# timeout=1 means: If one second goes by without a reply from the server,
	# the client assumes that either the client's ping or the server's pong is lost
	dest = gethostbyname(host)
	print("Pinging " + dest + " using Python:")
	print("")
	# Send ping requests to a server separated by approximately one second
	while 1 :
		delay = doOnePing(dest, timeout)
		print("Latest RTT: ", delay)
		if (len(rtt_data) > 0):
			print("MAX RTT: ", max(rtt_data))
			print("MIN RTT: ", min(rtt_data))
			print("AVG RTT: ", (sum(rtt_data)/len(rtt_data)))
		
		if (sent_count > 0):
			print("packet sent: ", sent_count)
			print("packet recv: ", recv_count)
			print("PACKET LOSS RATE: ", round(((sent_count-recv_count)/float(sent_count)) * 100, 2), "%")
			print()
		
		time.sleep(1)# one second
	return delay
	
ping("www.inven.co.kr")
