#!/usr/bin/python

import ast
import cgi
import os
import re
import socket
import sqlite3
import sys
import time

def sqlu(servpath, query):
	sqloconn = sqlite3.connect(servpath + "/private/" + "hosts.db")
	sqlocurs = sqloconn.cursor()
	
	try:
		sqlocurs.execute(query)
	except:
		pass
	
	try:
		sqlodata = sqlocurs.fetchall()
	except:
		sqlodata = []
	
	sqloconn.commit()
	sqlocurs.close()
	
	return sqlodata

def conf(confname, servpath):
	try:
		fileobjc = open(servpath + "/private/" + "pymons.conf", "r")
		linelist = fileobjc.readlines()
		fileobjc.close()
	except:
		linelist = []
	
	for lineitem in linelist:
		filelist = lineitem.split("=", 1)
		
		if (len(filelist) != 2):
			continue
		
		if (filelist[0].strip() == confname):
			return ast.literal_eval(filelist[1].strip())

def main():
	foldpath = "."
	password = conf("password", foldpath)
	sqlu(foldpath, "CREATE TABLE hosts (hname text, hdata text)")
	cliemode = "get"
	clierequ = "/"
	cliesend = ""
	formobjc = cgi.FieldStorage()
	
	if ("file" in formobjc):
		clierequ = formobjc["file"].value
	
	if ("Pass" in formobjc):
		cliemode = "post"
	
	if (cliemode == "post"):
		nameobjc = formobjc["Name"].value
		passobjc = formobjc["Pass"].value
		dataobjc = ast.literal_eval(formobjc["Data"].value)
		
		if ((password != "") and (passobjc == password)):
			sqlu(foldpath, "DELETE FROM hosts WHERE hname = \"%s\"" % (nameobjc))
			sqlu(foldpath, "INSERT INTO hosts VALUES (\"%s\", \"%s\")" % (nameobjc, str(dataobjc)))
	
	if (cliemode == "get"):
		if (clierequ == "/"):
			clierequ += "index.html"
		
		fileobjc = open(foldpath + "/public/" + os.path.normpath(clierequ), "r")
		htmlpage = fileobjc.read()
		fileobjc.close()
		
		cliesend += "Content-Type: text/html\r\n"
		cliesend += "\r\n"
		
		if (clierequ == "/index.html"):
			datalist = []
			htmldata = {}
			
			for dataitem in sqlu(foldpath, "SELECT hname, hdata FROM hosts ORDER BY hname"):
				datalist.append('{"name":"%s", "data":%s}' % (dataitem[0], dataitem[1]))
			
			htmldata["data"] = ("[" + ",\n".join(datalist) + "]")
			cliesend += (htmlpage % (htmldata))
		else:
			cliesend += htmlpage
	
	print(cliesend)

if (__name__ == "__main__"):
	main()
