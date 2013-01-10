#!/usr/bin/python

import re
import sys

linenumb = 1
srchterm = ""
srchfunc = ""

lastfnum = 0
lastfunc = ""

if (len(sys.argv) < 2):
	print("Usage: %s <regex search term> [<function name>]" % (sys.argv[0]))
	sys.exit(0)

if (len(sys.argv) >= 2):
	srchterm = sys.argv[1]

if (len(sys.argv) >= 3):
	srchfunc = sys.argv[2]

while (1):
	lineread = sys.stdin.readline()
	
	if (not lineread):
		break
	
	lineread = lineread.rstrip()
	
	if (re.match("^def .*$", lineread)):
		lastfnum = linenumb
		lastfunc = lineread
	
	if (re.match("^[\t ]+.*" + srchterm + ".*$", lineread)):
		if ((lastfunc == "") or (re.match("^def " + srchfunc + ".*$", lastfunc))):
			if (lastfunc != ""):
				print("[*] [%d] %s" % (lastfnum, lastfunc))
				
				lastfnum = 0
				lastfunc = ""
			
			print("[-] [%d] %s" % (linenumb, lineread))
	
	linenumb += 1
