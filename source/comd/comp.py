#!/usr/bin/python
import os
import sys

filelist = sys.argv[1:]
fileleng = len(filelist)

maxlnumb = 0
linelist = []

for filename in filelist:
	fobjitem = file(filename)
	fobjdata = fobjitem.readlines()
	fobjitem.close()
	
	linenumb = len(str(len(fobjdata)))
	maxlnumb = max(maxlnumb, linenumb)
	linelist.append(fobjdata)

try:
	int(os.environ["COLUMNS"])

except:
	print("# run the following command:\nexport COLUMNS")
	os._exit(0)

spacereq = (maxlnumb + 1 + 4)
maxsline = ((int(os.environ["COLUMNS"]) - (spacereq * fileleng)) / fileleng)
x = 1

while (1):
	quitflag = 1
	linenumb = str(x)
	outpstri = ""
	
	while (len(linenumb) < maxlnumb):
		linenumb = ("0" + linenumb)
	
	for lineitem in linelist:
		linestri = ""
		
		if (len(lineitem) > 0):
			linestri = lineitem.pop(0)
			quitflag = 0
		
		linestri = linestri.replace("\t", "    ")
		linestri = linestri[0:maxsline].rstrip()
		
		while (len(linestri) < maxsline):
			linestri += " "
		
		if (outpstri != ""):
			outpstri += " | "
		
		outpstri += (linenumb + ":" + linestri)
	
	if (quitflag == 1):
		break
	
	print(outpstri)
	x += 1
