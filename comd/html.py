#!/usr/bin/python

import sys

s = ""
l = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

while (1):
	c = sys.stdin.read(1)
	
	if (not c):
		break
	
	o = ord(c)
	
	if (o == 13):
		continue
	
	elif (c not in l):
		s += ("&#" + str(o) + ";")
	
	else:
		s += (c)

print(s)
