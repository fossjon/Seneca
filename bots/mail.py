#!/usr/bin/python

import os
import re
import select
import socket
import sys
import time
import urllib2

lasttime = 0; pagelist = [""]

def getspage():
	global pagelist
	
	outplist = []
	
	pagelist[0] = ("http://lists.fedoraproject.org/pipermail/arm/%s/date.html" % (time.strftime("%Y-%B")))
	
	for pageitem in pagelist:
		try:
			websobjc = urllib2.urlopen(pageitem, None, 10)
			dataread = websobjc.read().replace("\t", "").replace("\r", "").replace("\n", "")
			
			listlist = dataread.replace("<LI", "\n<LI").replace("</I", "</I>\n").split("\n")
			
			for listitem in listlist:
				listitem = listitem.strip()
				regxobjc = re.match("^<LI><A HREF=['\"]([^'\"]+)['\"]>([^<]+)</A><A [^<]+>[^<]+</A><I>([^<]+)</I>$", listitem)
				
				if (regxobjc):
					tempstri = ("[%s] by [%s] - %s/%s" % (regxobjc.group(2), regxobjc.group(3), os.path.dirname(pageitem), regxobjc.group(1)))
					outplist.append(tempstri)
		
		except KeyboardInterrupt:
			sys.exit(0)
		
		except:
			return []
	
	return outplist

def procuser(nickstri, mesgstri, datalist):
	global lasttime
	global pagelist
	
	outplist = []
	
	regxobjc = re.match("^:([^!]+)![^ ]+ privmsg ([^ ]+) :%s last$" % (nickstri), mesgstri, re.I)
	
	if (regxobjc):
		chanstri = regxobjc.group(2)
		
		try:
			lastindx = (len(datalist) - 1)
			outplist.append([chanstri, datalist[lastindx]])
		
		except:
			pass
	
	return outplist

sendline_last = 0; sendline_list = []

def sendline(circobjc, sendstri):
	global sendline_last
	global sendline_list
	
	prestime = time.time()
	tempstri = sendstri.strip()
	
	if (tempstri != ""):
		sendline_list.append(tempstri)
	
	if (((prestime - sendline_last) >= 1) and (len(sendline_list) > 0)):
		print("[S] [%s] %s" % (time.strftime("%Y/%m/%d-%H:%M:%S"), sendline_list[0]))
		circobjc.send(sendline_list[0] + "\r\n")
		
		sendline_list.pop(0)
		sendline_last = prestime

readline_data = ""

def readline(circobjc):
	global readline_data
	
	outpstri = ""
	(readlist, outplist, errolist) = select.select([circobjc], [], [], 0)
	
	if (circobjc in readlist):
		tempstri = circobjc.recv(2**20)
		
		if (not tempstri):
			readline_data = ""
			return None
		
		readline_data += tempstri
	
	try:
		newlindx = readline_data.index("\n")
	
	except:
		newlindx = -1
	
	if (newlindx != -1):
		outpstri = readline_data[:newlindx].strip()
		newlindx += 1
		readline_data = readline_data[newlindx:]
	
	return outpstri

procirco_last = 0

def procirco(circobjc, channame, lastmesg):
	global procirco_last
	
	prestime = time.time()
	
	if ((prestime - procirco_last) >= 60):
		sendline(circobjc, "JOIN " + channame)
		procirco_last = prestime
	
	regxobjc = re.match("^PING (.*)$", lastmesg)
	
	if (regxobjc):
		sendline(circobjc, "PONG " + regxobjc.group(1))

def newcirco(hostname, nickname):
	circobjc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	
	circobjc.connect((hostname, 6667))
	sendline(circobjc, "USER Alex * * : Bob")
	sendline(circobjc, "NICK %s" % (nickname))
	
	return circobjc

def main():
	global lasttime
	
	if (len(sys.argv) < 4):
		print("Usage: %s <host> <nick> <chan>" % (sys.argv[0]))
		sys.exit(0)
	
	hostname = sys.argv[1]; nickname = sys.argv[2]; channame = sys.argv[3]
	lastlist = None
	circobjc = None; circline = ""; circflag = 0
	
	while (1):
		circflag = 0
		prestime = time.time()
		
		if (circobjc == None):
			circobjc = newcirco(hostname, nickname)
		
		else:
			circline = readline(circobjc)
			
			if (circline == None):
				circobjc = None
			
			else:
				circflag = 1
				
				if (circline != ""):
					print("[R] [%s] %s" % (time.strftime("%Y/%m/%d-%H:%M:%S"), circline))
				
				procirco(circobjc, channame, circline)
				mesglist = procuser(nickname, circline, lastlist)
				
				for mesgitem in mesglist:
					sendline(circobjc, "PRIVMSG %s :%s" % (mesgitem[0], mesgitem[1]))
			
			if ((prestime - lasttime) >= (5 * 60)):
				templist = getspage()
				
				if (len(templist) > 0):
					if (lastlist == None):
						lastlist = templist
					
					for tempitem in templist:
						if (tempitem not in lastlist):
							sendline(circobjc, "PRIVMSG %s :%s" % (channame, tempitem))
					
					lastlist = templist
				
				lasttime = prestime
		
		sendline(circobjc, "")
		
		if (circflag == 0):
			time.sleep(1)

if (__name__ == "__main__"):
	main()
