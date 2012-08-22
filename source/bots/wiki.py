#!/usr/bin/python

import os
import re
import select
import socket
import sys
import time
import urllib2

lasttime = 0; pagelist = []

def getspage():
	global pagelist
	
	outplist = []
	
	for pageitem in pagelist:
		try:
			websobjc = urllib2.urlopen(pageitem, None, 10)
			dataread = websobjc.read().replace("\t", "").replace("\r", "").replace("\n", "")
			dataread = dataread.replace("<li", "\n<li").replace("</li", "</li>\n")
			webslist = dataread.split("\n")
			
			for listitem in webslist:
				if (re.match("^.*<li[ >].*\(cur\).*$", listitem)):
					edititem = re.sub("<[^>]*>", " ", listitem)
					edititem = edititem.replace("(", "<").replace(")", ">")
					edititem = re.sub("<[^>]*>", " ", edititem)
					edititem = edititem.strip()
					
					regxobjc = re.match("^(.*) ([^ ]+)$", edititem)
					
					if (regxobjc):
						pagename = pageitem.replace("action=history", "")
						username = regxobjc.group(2).strip()
						timedate = regxobjc.group(1).strip()
						
						headitem = ("[ %s ] was changed by [ %s ] on [ %s ]" % (pagename, username, timedate))
						outplist.append(headitem)
						
						break
		
		except KeyboardInterrupt:
			sys.exit(0)
		
		except:
			return []
	
	return outplist

def procuser(nickstri, mesgstri, datalist):
	global lasttime
	global pagelist
	
	outplist = []
	
	regxobjc = re.match("^:([^!]+)![^ ]+ privmsg ([^ ]+) :%s add (.*)$" % (nickstri), mesgstri, re.I)
	
	if (regxobjc):
		if (regxobjc.group(3) not in pagelist):
			outplist.append([regxobjc.group(2), "adding [ %s ]" % (regxobjc.group(3))])
			pagelist.append(regxobjc.group(3))
			lasttime = 0
	
	regxobjc = re.match("^:([^!]+)![^ ]+ privmsg ([^ ]+) :%s del (.*)$" % (nickstri), mesgstri, re.I)
	
	if (regxobjc):
		for x in range(len(pagelist) - 1, -1, -1):
			try:
				if (re.match(regxobjc.group(3), pagelist[x], re.I)):
					outplist.append([regxobjc.group(2), "deleting [ %s ]" % (pagelist[x])])
					pagelist.pop(x)
			
			except:
				pass
	
	regxobjc = re.match("^:([^!]+)![^ ]+ privmsg ([^ ]+) :%s all.*$" % (nickstri), mesgstri, re.I)
	
	if (regxobjc):
		try:
			for listitem in datalist:
				outplist.append([regxobjc.group(2), listitem])
		
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
