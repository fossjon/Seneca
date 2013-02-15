#!/usr/bin/python

# Version: 1.6
# Date: 14/02/2013 (dd/mm/yyyy)
# Name: Jon Chiappetta (jonc_mailbox@yahoo.ca)
#
# Execution notes (*you must*):
#
# - Allow and add any new package names to the given build tag
# - Resolve any circular dependency package issues

'''
	Define the needed imports
'''

import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib2

import bz2
import gzip
import koji
import rpm
import rpmUtils.miscutils
import string
import sqlite3
import xml.dom.minidom

''' ********************
    * Imported methods *
    ******************** '''

'''
	Generate a random path string (Koji source code)
'''

def _unique_path(prefix):
    """Create a unique path fragment by appending a path component
    to prefix.  The path component will consist of a string of letter and numbers
    that is unlikely to be a duplicate, but is not guaranteed to be unique."""
    # Use time() in the dirname to provide a little more information when
    # browsing the filesystem.
    # For some reason repr(time.time()) includes 4 or 5
    # more digits of precision than str(time.time())
    return '%s/%r.%s' % (prefix, time.time(),
                      ''.join([random.choice(string.ascii_letters) for i in range(8)]))

''' ********************************
    * Local script related methods *
    ******************************** '''

'''
	Print out a data item in string form
'''

def form_info(data_obj, simple_key):
	out_obj = {}
	for key_name in data_obj.keys():
		out_obj[key_name] = data_obj[key_name]
		if (key_name == simple_key):
			out_obj[key_name] = data_obj[key_name][0]
	return str(out_obj)

'''
	Read a given config file and parse thru the options
'''

def conf_file(file_name, old_opts):
	file_obj = open(file_name, "r")
	bool_dict = {"None":None,"True":True,"False":False}
	
	for line_item in file_obj.readlines():
		line_item = line_item.replace("\t"," ").replace("\"","'")
		line_item = line_item.replace("[","<").replace("]",">")
		line_item = line_item.replace("(","<").replace(")",">")
		line_item = line_item.strip()
		
		if (re.match("^#[ ]*.*$", line_item)):
			continue
		
		opts_key = "" ; opts_val = ""
		
		# Boolean
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*([A-Z][a-z]+)$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = bool_dict[regx_obj.group(2)]
		# Integer
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*([0-9]+)$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = int(regx_obj.group(2))
		# String
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*'(.+)'$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = regx_obj.group(2)
		# List of strings
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*<'(.+)'>$", line_item)
		if (regx_obj):
			list_strip = re.sub("'[ ]*,[ ]*'", "','", regx_obj.group(2))
			opts_key = regx_obj.group(1) ; opts_val = list_strip.split("','")
		# OS path expansion
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*os.path.expanduser<'(.+)'>$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = os.path.expanduser(regx_obj.group(2))
		
		if ((opts_key != "") and (opts_val != "")):
			old_opts[opts_key] = opts_val
	
	file_obj.close()
	
	return old_opts

'''
	Define a db method so other scripts can check our recorded state of packages
'''

def local_db(rpm_data, pres_time):
	db_conn = sqlite3.connect(".koji-follow.state.db")
	db_curs = db_conn.cursor()
	
	try:
		db_curs.execute("CREATE TABLE packages (pkg_name text, pkg_info text, update_time int);")
	except:
		pass
	
	if (rpm_data):
		db_curs.execute("DELETE FROM packages WHERE pkg_name = '%s';" % (rpm_data["srpm_name"]))
		db_curs.execute("INSERT INTO packages VALUES ('%s', \"%s\", %d);" % (rpm_data["srpm_name"], str(rpm_data), pres_time))
	else:
		db_curs.execute("DELETE FROM packages WHERE update_time < %d;" % (pres_time))
	
	db_conn.commit()
	db_conn.close()

''' **********************************
    * General script related methods *
    ********************************** '''

'''
	Delete the given filename
'''

def delete(file_name):
	if (not file_name):
		return 1
	sys.stderr.write("\t" + "[info] delete: " + file_name + "\n")
	try:
		os.unlink(file_name)
	except:
		pass
	return 0

'''
	Clear the rpmbuild folder structure
'''

def wipe_tree():
	rpmb_dir = os.path.expanduser("~/rpmbuild")
	try:
		for rpmb_item in os.listdir(rpmb_dir):
			subs_dir = ("%s/%s" % (rpmb_dir, rpmb_item))
			try:
				os.unlink(subs_dir)
			except:
				pass
			try:
				shutil.rmtree(subs_dir)
			except:
				pass
	except:
		pass

'''
	Download a given url link to a specified filename
'''

def download_file(url_str, file_name):
	if (file_name):
		if (os.path.exists(file_name)):
			return 0
	
	sys.stderr.write("\t" + "[info] downloading: " + ("[%s] -> [%s]" % (url_str, file_name)) + "\n")
	
	try:
		if (file_name):
			file_obj = open(file_name, "w")
		else:
			data_str = ""
		url_obj = urllib2.urlopen(url_str)
		
		while (1):
			read_data = url_obj.read(8192)
			if (not read_data):
				break
			if (file_name):
				file_obj.write(read_data)
			else:
				data_str += read_data
		
		url_obj.close()
		if (file_name):
			file_obj.close()
		else:
			return data_str
	
	except:
		sys.stderr.write("\t" + "[error] download" + "\n")
		return 1
	
	return 0

'''
	Build a source rpm file based on a given spec file
'''

def rebuild_srpm(arch_name, rpm_spec, rand_rels):
	if (rand_rels == True):
		try:
			file_obj = open(rpm_spec, "r")
			line_list = file_obj.readlines()
			file_obj.close()
			rels_flag = 0
			file_obj = open(rpm_spec, "w")
			for line_item in line_list:
				tmp_line = line_item.replace("\t"," ").strip()
				regx_obj = re.match("^Release: .*$", tmp_line, re.I)
				if ((regx_obj) and (rels_flag == 0)):
					tmp_line = re.sub("\.[0-9]+kf$", "", tmp_line)
					line_item = ("%s.%skf\n" % (tmp_line, time.strftime("%y%m%d%H%M")))
					rels_flag = 1
				file_obj.write(line_item)
			file_obj.close()
		except:
			sys.stderr.write("\t" + "[error] rpm_spec: " + spec_file + "\n")
			return ""
	try:
		srpm_out = subprocess.check_output(["/usr/bin/rpmbuild", "-bs", "--target", arch_name, rpm_spec], stderr=subprocess.STDOUT)
		for out_line in srpm_out.split("\n"):
			out_line = out_line.replace("\t"," ").strip()
			regx_obj = re.match("^wrote: [ ]*(.*)$", out_line, re.I)
			if (regx_obj):
				return regx_obj.group(1)
	except:
		sys.stderr.write("\t" + "[error] rpm_build: " + spec_file + "\n")
	return ""


'''
	Loop thru the given rpm file headers and return any listed package requirements
'''

def rpm_header(file_name, req_rels):
	info_list = [] ; req_list = []
	compare_map = {"":"", "<":"LT", "<>":"LG", "<=":"LE", "<>=":"LGE", ">":"GT", ">=":"GE", "=":"EQ"}
	rpm_trans = rpm.ts()
	
	try:
		file_desc = os.open(file_name, os.O_RDONLY)
		rpm_header = rpm_trans.hdrFromFdno(file_desc)
		os.close(file_desc)
		
		info_list.append([rpm_header[rpm.RPMTAG_NAME], rpm_header[rpm.RPMTAG_RELEASE]])
		
		for x in range(0, len(rpm_header[rpm.RPMTAG_REQUIRES])):
			req_name = rpm_header[rpm.RPMTAG_REQUIRES][x]
			req_flag = ""
			
			if (rpm_header[rpm.RPMTAG_REQUIREFLAGS][x] & rpm.RPMSENSE_LESS):
				req_flag += "<"
			if (rpm_header[rpm.RPMTAG_REQUIREFLAGS][x] & rpm.RPMSENSE_GREATER):
				req_flag += ">"
			if (rpm_header[rpm.RPMTAG_REQUIREFLAGS][x] & rpm.RPMSENSE_EQUAL):
				req_flag += "="
			
			req_epoch = None
			req_vers = None
			
			if (rpm_header[rpm.RPMTAG_REQUIREVERSION][x]):
				req_vers = rpm_header[rpm.RPMTAG_REQUIREVERSION][x]
			
			req_list.append([req_name, compare_map[req_flag], req_epoch, req_vers, req_rels])
	
	except:
		pass
	
	return [info_list, req_list]

'''
	Attempt to decompress a compressed file format
'''

def decomp_file(file_name):
	comp_obj = None
	
	try:
		comp_obj = bz2.BZ2File(file_name, "rb")
		comp_obj.read(1) ; comp_obj.close()
		comp_obj = bz2.BZ2File(file_name, "rb")
	except:
		try:
			comp_obj = gzip.open(file_name, "rb")
			comp_obj.read(1) ; comp_obj.close()
			comp_obj = gzip.open(file_name, "rb")
		except:
			comp_obj = None
	
	if (comp_obj):
		plain_name = re.sub("\.[bg]z[0-9A-Za-z]*$", "", file_name)
		
		sys.stderr.write("\t" + "[info] decompressing: " + ("[%s] -> [%s]" % (file_name, plain_name)) + "\n")
		
		file_obj = open(plain_name, "wb")
		
		while (1):
			comp_data = comp_obj.read(8192)
			if (not comp_data):
				break
			file_obj.write(comp_data)
		
		file_obj.close()
		comp_obj.close()
		
		return plain_name
	
	return file_name

'''
	Get the latest repodata files for a given arch and release tag
'''

def get_repodata(koji_url, arch_name, target_name, file_name):
	try:
		repodata_url = ("%s/repos/%s/latest/%s/repodata/repomd.xml" % (koji_url, target_name, arch_name))
		url_data = download_file(repodata_url, "").replace("\0","").replace("\t","").replace("\r","").replace("\n","").replace("\"","'")
		
		reg_obj = re.match("^.*'([^']*primary.sqlite[^']*)'.*$", url_data, re.I)
		repo_file = reg_obj.group(1)
		package_url = ("%s/repos/%s/latest/%s/%s" % (koji_url, target_name, arch_name, repo_file))
	
	except:
		sys.stderr.write("\t" + "[error] repodata_meta: " + repodata_url + "\n")
		return ""
	
	repofile_name = os.path.basename(repo_file)
	delete(repofile_name)
	if (download_file(package_url, repofile_name) != 0):
		sys.stderr.write("\t" + "[error] repodata_db: " + package_url + "\n")
		return ""
	
	final_name = decomp_file(repofile_name)
	if (final_name != repofile_name):
		delete(repofile_name)
	if (final_name != file_name):
		try:
			os.rename(final_name, file_name)
		except:
			sys.stderr.write("\t" + "[error] rename: " + final_name + " -> " + file_name + "\n")
			return ""
		final_name = file_name
	
	return final_name

'''
	Translate any required capability or binary package names to a unique list of source package names
'''

def map_cap(cap_list, db_name):
	final_list = []
	
	db_conn = sqlite3.connect(db_name)
	db_curs = db_conn.cursor()
	
	for x in range(0, len(cap_list)):
		cap_name = ""
		for cap_type in ["provides", "files"]:
			try:
				db_list = db_curs.execute("SELECT packages.rpm_sourcerpm FROM %s JOIN packages ON packages.pkgKey = %s.pkgKey WHERE %s.name = '%s';" % (cap_type, cap_type, cap_type, cap_list[x][0]))
			except:
				db_list = []
			for pkg_item in db_list:
				(rpm_name, rpm_vers, rpm_rels, rpm_epoch, rpm_arch) = rpmUtils.miscutils.splitFilename(str(pkg_item[0]))
				cap_name = rpm_name
		cap_list[x][0] = cap_name
	
	db_conn.close()
	
	for cap_item in cap_list:
		if (cap_item[0]):
			final_flag = 0
			for final_item in final_list:
				if (final_item[0] == cap_item[0]):
					final_flag = 1
			if (final_flag == 0):
				final_list.append(cap_item)
	
	return final_list

'''
	Get a list of package information and urls for a given package name
'''

def get_pkgs(pkg_name, db_name):
	final_list = []
	arch_flag = False
	
	db_conn = sqlite3.connect(db_name)
	db_curs = db_conn.cursor()
	
	try:
		db_list = db_curs.execute("SELECT rpm_sourcerpm,name,epoch,version,release,arch,location_base,location_href FROM packages WHERE location_href LIKE '%%%s/%%';" % (pkg_name))
	except:
		db_list = []
	
	for pkg_item in db_list:
		(rpm_name, rpm_vers, rpm_rels, rpm_epoch, rpm_arch) = rpmUtils.miscutils.splitFilename(str(pkg_item[0]))
		if (rpm_name != pkg_name):
			continue
		if ((rpm_epoch == 0) or (rpm_epoch == "0") or (rpm_epoch == "None")):
			rpm_epoch = None
		
		if (len(final_list) < 1):
			pref_list = []
			for url_item in str(pkg_item[7]).split("/"):
				if (url_item == pkg_name):
					break
				pref_list.append(url_item)
			item_url = ("%s/%s/%s/%s/%s/%s/%s" % (str(pkg_item[6]), "/".join(pref_list), pkg_name, rpm_vers, rpm_rels, rpm_arch, str(pkg_item[0])))
			item_info = {"name":pkg_name, "epoch":rpm_epoch, "version":rpm_vers, "release":rpm_rels, "arch":rpm_arch, "url":item_url}
			item_info["nvr"] = ("%s-%s-%s" % (item_info["name"], item_info["version"], item_info["release"]))
			final_list.append(item_info)
		
		rpm_epoch = str(pkg_item[2])
		if ((rpm_epoch == 0) or (rpm_epoch == "0") or (rpm_epoch == "None")):
			rpm_epoch = None
		item_url = ("%s/%s" % (str(pkg_item[6]), str(pkg_item[7])))
		item_info = {"name":str(pkg_item[1]), "epoch":rpm_epoch, "version":str(pkg_item[3]), "release":str(pkg_item[4]), "arch":str(pkg_item[5]), "url":item_url}
		item_info["nvr"] = ("%s-%s-%s" % (item_info["name"], item_info["version"], item_info["release"]))
		final_list.append(item_info)
		
		if ((item_info["arch"] != "src") and (item_info["arch"] != "noarch")):
			arch_flag = True
	
	db_conn.close()
	
	return (arch_flag, final_list)

''' ************************
    * Koji related methods *
    ************************ '''

'''
	Get the latest build state for a given package nvr
'''

def koji_state(pkg_nvr, koji_obj):
	build_info = {"state":-1, "task_id":-1}
	
	# koji.BUILD_STATES['s'] = {0:'BUILDING',1:'COMPLETE',2:'DELETED',3:'FAILED',4:'CANCELED'}
	# koji.TASK_STATES['s'] = {0:'FREE',1:'OPEN',2:'CLOSED',3:'CANCELED',4:'ASSIGNED',5:'FAILED'}
	
	try:
		tmp_info = koji_obj.getBuild(pkg_nvr)
		
		try:
			build_info["state"] = tmp_info["state"]
			if ((build_info["state"] != 0) and (build_info["state"] != 1)):
				build_info["state"] = -3
		except:
			build_info["state"] = -4
		
		try:
			build_info["task_id"] = tmp_info["task_id"]
		except:
			build_info["task_id"] = -3
	
	except:
		build_info["state"] = -2
		build_info["task_id"] = -2
	
	build_info["sent_nvr"] = pkg_nvr
	
	return build_info

'''
	Reorder and organize the que items into a hierarchical list based on dependencies
'''

def process_que(inpt_list):
	for que_key in inpt_list.keys():
		que_item = inpt_list[que_key]
		tmp_list = []
		for dep_name in que_item["dep_list"]:
			for tmp_key in inpt_list.keys():
				tmp_item = inpt_list[tmp_key]
				if (tmp_item["srpm_name"] == dep_name):
					tmp_list.append(dep_name)
		que_item["dep_list"] = tmp_list
	
	name_list = [] ; value_list = []
	for que_key in inpt_list.keys():
		que_item = inpt_list[que_key]
		name_list.append(que_item["srpm_name"])
		value_list.append(que_item)
	
	wait_flag = 0
	ready_list = [] ; wait_list = []
	while (1):
		tmp_list = []
		for x in range(0, len(name_list)):
			if (name_list[x]):
				dep_flag = 0
				for dep_name in value_list[x]["dep_list"]:
					if (dep_name in name_list):
						dep_flag = 1
				if (dep_flag == 0):
					tmp_list.append(value_list[x])
					name_list[x] = None
		if (len(tmp_list) < 1):
			break
		for tmp_item in tmp_list:
			if (wait_flag == 0):
				ready_list.append(tmp_item)
			else:
				wait_list.append(tmp_item)
		wait_flag = 1
	
	error_list = []
	for x in range(0, len(name_list)):
		if (name_list[x]):
			error_list.append(value_list[x])
	
	return (ready_list, wait_list, error_list)

'''
	Parse thru the root.log file of a failed build and check for any package requires
'''

def proc_error(info_obj, koji_obj):
	final_list = []
	
	try:
		if (not "task_id" in info_obj.keys()):
			return final_list
		task_obj = koji_obj.getTaskInfo(info_obj["task_id"])
		
		if (not "id" in task_obj.keys()):
			return final_list
		child_list = koji_obj.listTasks(opts={"parent":task_obj["id"]}, queryOpts={"limit":4})
		
		for child_task in child_list:
			if (not "id" in child_task.keys()):
				continue
			log_list = koji_obj.downloadTaskOutput(child_task["id"], "root.log")
			
			for log_line in log_list.split("\n"):
				log_line = log_line.replace("\t"," ").strip()
				log_line = re.sub("\(.*$", "", log_line)
				if (" Error: Package: " in log_line):
					regx_obj = re.match("^.* Error: Package: (.*)-[^-]+-[^-]+$", log_line, re.I)
					if (regx_obj):
						pkg_name = re.sub("^[0-9]+:", "", regx_obj.group(1))
						final_list.append([pkg_name.strip()])
	
	except:
		pass
	
	return final_list

'''
	Attempt to find either the first or latest build attempt for a given pkg name
'''

def build_item(pkg_name, koji_tag, koji_obj, init_item=True):
	final_item = None
	
	try:
		search_list = koji_obj.search(pkg_name, "package", "glob")
	except:
		search_list = []
	
	if (len(search_list) == 1):
		try:
			build_list = koji_obj.listBuilds(packageID=search_list[0]["id"])
		except:
			build_list = []
		
		for build_info in build_list:
			try:
				tag_list = koji_obj.listTags(build_info["nvr"])
			except:
				tag_list = []
			
			if (init_item == True):
				if (build_info["state"] != 1):
					continue
				for tag_item in tag_list:
					if (tag_item["name"] == koji_tag):
						if (not final_item):
							final_item = build_info
						elif (build_info["creation_ts"] < final_item["creation_ts"]):
							final_item = build_info
			
			else:
				tag_numb = re.sub("[^0-9]", "", koji_tag)
				regx_end = re.match("^.*\.fc%s$" % (tag_numb), build_info["release"], re.I)
				regx_mid = re.match("^.*\.fc%s\..*$" % (tag_numb), build_info["release"], re.I)
				if ((not regx_end) and (not regx_mid)):
					continue
				if (not final_item):
					final_item = build_info
				elif (build_info["creation_ts"] > final_item["creation_ts"]):
					final_item = build_info
	
	return final_item

'''
	Insert a qued pkg item in order related to when it was built
'''

def sorted_insert(insert_item, input_list):
	final_list = []
	insert_flag = 0
	
	for input_item in input_list:
		if ((insert_item[0] < input_item[0]) and (insert_flag == 0)):
			final_list.append(insert_item)
			insert_flag = 1
		final_list.append(input_item)
	
	if (insert_flag == 0):
		final_list.append(insert_item)
	
	return final_list

'''
	Upload, import, tag, and skip any noarch detected packages
'''

def import_noarch(que_item, block_list, koji_tag, koji_obj):
	noarch_flag = 0
	task_info = que_item["task_info"]
	dev_null = open("/dev/null", "r+")
	
	sys.stderr.write("\t" + "[info]" + " noarch: " + str(que_item) + "\n")
	
	if (noarch_flag == 0):
		if (que_item["srpm_name"] in block_list):
			sys.stderr.write("\t" + "[error] noarch_excluded" + "\n")
			noarch_flag = 1
	
	''' Download all of the noarch rpm files '''
	
	if (noarch_flag == 0):
		for pkg_item in task_info:
			rpm_file = os.path.basename(pkg_item["url"])
			if (download_file(pkg_item["url"], rpm_file) != 0):
				noarch_flag = 1
				break
			if (subprocess.call(["/bin/rpm", "-K", rpm_file], stdout=dev_null, stderr=subprocess.STDOUT) != 0):
				sys.stderr.write("\t" + "[error] noarch_verify: " + ("[%s] -> [%s]" % (pkg_item["url"], rpm_file)) + "\n")
				noarch_flag = 1
				break
	
	''' Upload and import the related rpm files '''
	
	if (noarch_flag == 0):
		for y in range(0, 2):
			for pkg_item in task_info:
				if ((y == 0) and (pkg_item["arch"] != "src")):
					continue
				if ((y != 0) and (pkg_item["arch"] == "src")):
					continue
				
				pres_dir = os.getcwd()
				rpm_name = os.path.basename(pkg_item["url"])
				file_path = ("%s/%s" % (pres_dir, rpm_name))
				server_dir = _unique_path("cli-import")
				
				#sys.stderr.write("\t" + "[info] import: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
				
				try:
					koji_obj.uploadWrapper(file_path, server_dir)
					try:
						koji_obj.importRPM(server_dir, rpm_name)
					except:
						sys.stderr.write("\t" + "[error] noarch_import: " + ("[%s] -> [%s]" % (server_dir, rpm_name)) + "\n")
				except:
					sys.stderr.write("\t" + "[error] noarch_upload: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
	
	''' Tag the source rpm name '''
	
	if (noarch_flag == 0):
		for pkg_item in task_info:
			if (pkg_item["arch"] == "src"):
				#sys.stderr.write("\t" + "[info] tag: " + ("[%s] <- [%s]" % (conf_opts["tag_name"], pkg_item["nvr"])) + "\n")
				
				try:
					koji_obj.tagBuild(koji_tag, pkg_item["nvr"])
				except:
					sys.stderr.write("\t" + "[error] noarch_tag: " + ("[%s] <- [%s]" % (conf_opts["tag_name"], pkg_item["nvr"])) + "\n")
	
	dev_null.close()

'''
	Que a package to be built
'''

def que_build(target, que_obj, koji_obj):
	pres_dir = os.getcwd()
	rpm_name = os.path.basename(que_obj["task_info"][0]["url"])
	file_path = ("%s/%s" % (pres_dir, rpm_name))
	server_dir = _unique_path("cli-build")
	opts = {}
	
	sys.stdout.write("\t" + "[info] que_build: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
	
	try:
		koji_obj.uploadWrapper(file_path, server_dir, callback=None)
		server_dir = ("%s/%s" % (server_dir, os.path.basename(file_path)))
		try:
			koji_obj.build(server_dir, target, opts, priority=5)
			return 1
		except:
			sys.stderr.write("\t" + "[error] build_que" + "\n")
	except:
		sys.stderr.write("\t" + "[error] build_upload" + "\n")
	
	return 0

''' *****************************
    * Primary execution methods *
    ***************************** '''

'''
	The main method containing the continuous package version check/watch loop
'''

def main(args):
	''' Define the commonly referenced variables '''
	
	try:
		conf_opts = conf_file(sys.argv[1], {})
		sys.stderr.write(str(conf_opts) + "\n\n")
	except:
		sys.stderr.write("Usage: %s </path/to/conf>\n" % (os.path.basename(sys.argv[0])))
		sys.exit(1)
	
	wait_time = (2 * 60)
	que_list = {}
	dev_null = open("/dev/null", "r+")
	
	''' ********************************
	    * Outer infinite checking loop *
	    ******************************** '''
	
	while (1):
		loop_flag = 0
		conf_opts = conf_file(sys.argv[1], conf_opts)
		
		sys.stderr.write("[info] Starting outer check loop..." + "\n")
		
		if (conf_opts["retry_flag"] == True):
			for que_key in que_list.keys():
				que_list[que_key]["que_flag"] = False
		
		#delete any of the un-needed/un-used files in the pwd
		
		''' *******************************************************************************************************
		    * Download the latest repodata files so we can process packages and convert any "BuildRequires" names *
		    ******************************************************************************************************* '''
		
		if (loop_flag == 0):
			primary_repo = ""
			
			try:
				primary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["primary_url"]))
				release_info = primary_obj.getBuildTarget(conf_opts["tag_name"])
				
				try:
					primary_repo = ("primary.%s.db" % (release_info["build_tag_name"]))
					primary_repo = get_repodata(conf_opts["primary_url"], conf_opts["primary_arch"], release_info["build_tag_name"], primary_repo)
					
					if (not os.path.exists(primary_repo)):
						sys.stderr.write("\t" + "[error] repodata_file: " + primary_repo + "\n")
						loop_flag = 1
				
				except:
					sys.stderr.write("\t" + "[error] repodata_taginfo: " + conf_opts["tag_name"] + "\n")
					loop_flag = 1
			
			except:
				sys.stderr.write("\t" + "[error] build_target: " + conf_opts["tag_name"] + "\n")
				loop_flag = 1
		
		''' **********************************************************
		    * Get a list of the latest tagged packages for each arch *
		    ********************************************************** '''
		
		if (loop_flag == 0):
			sys.stderr.write("[info] latest_tagged: " + conf_opts["tag_name"] + "\n")
			
			try:
				primary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["primary_url"]))
				primary_tags = primary_obj.listTagged(conf_opts["tag_name"], inherit=False, latest=True)
				
				secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
				secondary_tags = secondary_obj.listTagged(conf_opts["tag_name"], inherit=False, latest=True)
				
				secondary_dic = {}
				for secondary_item in secondary_tags:
					secondary_dic[secondary_item["name"]] = secondary_item
			
			except:
				sys.stderr.write("\t" + "[error] latest_tagged" + "\n")
				loop_flag = 1
		
		''' **********************************************************************
		    * Compare each pkg version and record any items that are out of date *
		    ********************************************************************** '''
		
		if (loop_flag == 0):
			check_list = {} ; extra_list = []
			x = 0 ; l = len(primary_tags)
			
			for primary_item in primary_tags:
				x += 1
				add_flag = 1
				(arch_found, task_info) = get_pkgs(primary_item["name"], primary_repo)
				
				if (add_flag != 0):
					if (len(task_info) < 1):
						sys.stderr.write("\t" + "[error]: " + ("[%d/%d] tag_not_repo: " % (x, l)) + primary_item["name"] + "\n")
						add_flag = 0
				
				if (add_flag != 0):
					primary_item = task_info[0]
					if (not primary_item["name"] in secondary_dic.keys()):
						add_flag = 2
					else:
						secondary_item = secondary_dic[primary_item["name"]]
						if (len(primary_item.keys()) > 3):
							evr_alpha = (str(secondary_item["epoch"]), secondary_item["version"], secondary_item["release"])
							evr_beta = (str(primary_item["epoch"]), primary_item["version"], primary_item["release"])
							if (rpm.labelCompare(evr_alpha, evr_beta) < 0):
								add_flag = 2
					pre_list = []
				
				if (add_flag == 2):
					try:
						last_build = build_item(primary_item["name"], conf_opts["tag_name"], secondary_obj, init_item=False)
						if (last_build):
							state_info = koji_state(last_build["nvr"], secondary_obj)
						else:
							state_info = koji_state(primary_item["nvr"], secondary_obj)
						if (state_info["state"] == 1):
							sys.stderr.write("\t" + "[info]: " + ("[%d/%d] build_completed: " % (x, l)) + primary_item["nvr"] + "\n")
							add_flag = 0
						elif (state_info["state"] == -3):
							error_list = proc_error(state_info, secondary_obj)
							prio_list = map_cap(error_list, primary_repo)
							for prio_item in prio_list:
								pre_list.append(prio_item[0])
							if (len(pre_list) > 0):
								extra_list.append(["error",pre_list])
					except:
						sys.stderr.write("\t" + "[error]: " + ("[%d/%d] koji_state: " % (x, l)) + primary_item["nvr"] + "\n")
						add_flag = 0
				
				if (add_flag == 2):
					que_item = {"srpm_name":primary_item["name"], "task_info":task_info, "que_state":state_info, "dep_list":pre_list, "prio_flag":False}
					sys.stderr.write("\t" + "[info]: " + ("[%d/%d] adding: " % (x, l)) + primary_item["nvr"] + "\n")
					if (arch_found == False):
						extra_list.append(["noarch",que_item])
					else:
						check_list[primary_item["name"]] = que_item
		
		''' ***********************************************
		    * Process any noarch or error tagged packages *
		    *********************************************** '''
		
		if (loop_flag == 0):
			try:
				secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
				secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
			except:
				sys.stderr.write("\t" + "[error] noarch_login" + "\n")
				loop_flag = 1
		
		if (loop_flag == 0):
			seen_list = []
			x = 0 ; l = len(extra_list)
			
			for extra_item in extra_list:
				x += 1
				
				if (extra_item[0] == "noarch"):
					import_noarch(extra_item[1], conf_opts["excl_list"], conf_opts["tag_name"], secondary_obj)
				
				elif (extra_item[0] == "error"):
					for pre_item in extra_item[1]:
						if (pre_item in seen_list):
							continue
						
						for primary_item in primary_tags:
							if (primary_item["name"] != pre_item):
								continue
							(arch_found, task_info) = get_pkgs(primary_item["name"], primary_repo)
							if (len(task_info) < 1):
								continue
							primary_item = task_info[0]
							
							sys.stderr.write("\t" + "[info]: " + ("[%d/%d] priority: " % (x, l)) + primary_item["nvr"] + "\n")
							
							state_info = koji_state(primary_item["nvr"], secondary_obj)
							que_item = {"srpm_name":primary_item["name"], "task_info":task_info, "que_state":state_info, "dep_list":[], "prio_flag":True}
							check_list[primary_item["name"]] = que_item
						
						seen_list.append(pre_item)
		
		''' **********************************************
		    * Inner processing loop for missing packages *
		    ********************************************** '''
		
		if (loop_flag == 0):
			update_time = int(time.time())
			x = 0 ; l = len(check_list.keys())
			
			sys.stderr.write("[info] Starting inner processing loop..." + "\n")
			
			for check_key in check_list.keys():
				x += 1
				skip_flag = 0
				que_item = check_list[check_key]
				task_info = que_item["task_info"]
				
				sys.stderr.write("\t" + "[info] processing: " + ("[%d/%d]: " % (x, l)) + que_item["srpm_name"] + "\n")
				
				''' *************************************************************************************************
				    * Download and rebuild the given source rpm file for our arch to get the needed "BuildRequires" *
				    ************************************************************************************************* '''
				
				if (skip_flag == 0):
					srpm_file = os.path.basename(task_info[0]["url"])
					rpm_code = 1
					
					if (os.path.exists(srpm_file)):
						wipe_tree()
						rpm_code = subprocess.call(["/bin/rpm", "-i", srpm_file], stdout=dev_null, stderr=subprocess.STDOUT)
					
					if (rpm_code != 0):
						if (os.path.exists(srpm_file)):
							delete(srpm_file)
						if (download_file(task_info[0]["url"], srpm_file) == 0):
							wipe_tree()
							rpm_code = subprocess.call(["/bin/rpm", "-i", srpm_file], stdout=dev_null, stderr=subprocess.STDOUT)
					
					if (rpm_code == 0):
						try:
							spec_path = os.path.expanduser("~/rpmbuild/SPECS")
							spec_list = os.listdir(spec_path)
							spec_file = (spec_path + "/" + spec_list[0])
							rpmb_file = rebuild_srpm(conf_opts["target_arch"], spec_file, que_item["prio_flag"])
							
							if (rpmb_file):
								rpm_info = rpm_header(rpmb_file, None)
								que_item["cap_list"] = rpm_info[1]
							
							else:
								sys.stderr.write("\t" + "[error] rpm_build: " + ("[%s] -> [%s]" % (spec_file, srpm_file)) + "\n")
								skip_flag = 1
						
						except:
							sys.stderr.write("\t" + "[error] rpm_spec: " + srpm_file + "\n")
							skip_flag = 1
					
					else:
						sys.stderr.write("\t" + "[error] rpm_install: " + srpm_file + "\n")
						skip_flag = 1
				
				''' *******************************************************************************************************
				    * Translate any capability or binary package requires to a source package name and append it as a dep *
				    ******************************************************************************************************* '''
				
				if (skip_flag == 0):
					req_list = map_cap(que_item["cap_list"], primary_repo)
					que_item["cap_list"] = []
					for req_item in req_list:
						que_item["dep_list"].append(req_item[0])
				
				''' **************************************************************
				    * Restore any previous que info to prevent redundant actions *
				    ************************************************************** '''
				
				if (skip_flag == 0):
					que_item["que_flag"] = False
					
					if (check_key in que_list.keys()):
						prev_item = que_list[check_key]
						prev_task = prev_item["task_info"]
						
						que_item["que_flag"] = prev_item["que_flag"]
						
						if (len(prev_item["dep_list"]) != len(que_item["dep_list"])):
							que_item["que_flag"] = False
						if (prev_task[0]["nvr"] != task_info[0]["nvr"]):
							que_item["que_flag"] = False
				
				''' *************************************************************************************
				    * Process any packages marked as a priority and clear any flags that would block it *
				    ************************************************************************************* '''
				
				if (skip_flag == 0):
					if (que_item["prio_flag"] == True):
						que_item["cap_list"] = []
						que_item["dep_list"] = []
						task_info[0]["url"] = rpmb_file
						srpm_file = os.path.basename(task_info[0]["url"])
						try:
							shutil.copyfile(task_info[0]["url"], srpm_file)
						except:
							sys.stderr.write("\t" + "[error] rpm_copy: " + ("[%s] -> [%s]" % (task_info[0]["url"], srpm_file)) + "\n")
							skip_flag = 1
				
				''' *******************************************************************************
				    * Append this que item, set any last minute flags, and write it out to the db *
				    ******************************************************************************* '''
				
				if (skip_flag == 0):
					if (que_item["que_state"]["state"] == 0):
						que_item["que_flag"] = True
					if (que_item["srpm_name"] in conf_opts["excl_list"]):
						que_item["que_flag"] = True
					sys.stderr.write("\t" + "[info] processed: " + form_info(que_item,"task_info") + "\n")
					que_list[check_key] = que_item
			
			for que_key in que_list.keys():
				if (not que_key in check_list.keys()):
					del que_list[que_key]
			
			for que_key in que_list.keys():
				local_db(que_list[que_key], update_time)
			local_db(None, update_time)
		
		''' ****************************************************************
		    * Inner que'ing loop for the first level of processed packages *
		    **************************************************************** '''
		
		if (loop_flag == 0):
			(que_ready, que_wait, que_error) = process_que(que_list)
			
			sys.stdout.write("[info] Starting inner que loop..." + "\n")
			
			while (1):
				conf_opts = conf_file(sys.argv[1], conf_opts)
				
				str_out = ("Que Round :: ready [%d] -- waiting [%d] -- errors [%d]" % (len(que_ready), len(que_wait), len(que_error)))
				str_len = len(str_out) ; sym_out = ("#" * str_len)
				sys.stdout.write("\n##%s##\n# %s #\n##%s##\n\n" % (sym_out, str_out, sym_out))
				
				''' Login and authenticate to the Koji server '''
				
				try:
					primary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["primary_url"]))
					secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
					secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
				except:
					sys.stderr.write("\t" + "[error] build_login" + "\n")
					time.sleep(wait_time)
					continue
				
				''' Check for any solvable error packages or exit now if our que list is empty '''
				
				if (len(que_ready) < 1):
					if (len(que_error) < 1):
						while (len(que_wait) > 0):
							sys.stdout.write(("que[w] [-%d/%d]: " % (len(que_wait), conf_opts["que_limit"])) + form_info(que_wait[0],"task_info") + "\n")
							que_wait.pop(0)
						break
					else:
						que_sort = []
						while (len(que_error) > 0):
							init_build = build_item(que_error[0]["srpm_name"], conf_opts["tag_name"], primary_obj, init_item=True)
							if (init_build):
								que_sort = sorted_insert([init_build["creation_ts"], que_error[0]], que_sort)
							else:
								sys.stdout.write(("que[e] [-%d/%d]: " % (len(que_error), conf_opts["que_limit"])) + form_info(que_error[0],"task_info") + "\n")
							que_error.pop(0)
						for que_item in que_sort:
							que_ready.append(que_item[1])
				
				''' Get a count of our active tasks '''
				
				try:
					user_info = secondary_obj.getLoggedInUser()
					secondary_tasks = secondary_obj.listTasks(opts={"state":[0,1], "method":"build", "owner":user_info["id"]}, queryOpts={"limit":900})
					que_length = len(secondary_tasks)
					if (que_length >= conf_opts["que_limit"]):
						raise NameError("TooManyTasks")
				except:
					sys.stderr.write("[info] task_list/que_max: " + ("[%d/%d]" % (que_length, conf_opts["que_limit"])) + "\n")
					time.sleep(wait_time)
					continue
				
				''' Que any new packages now '''
				
				while ((len(que_ready) > 0) and (que_length < conf_opts["que_limit"])):
					pkg_name = que_ready[0]["srpm_name"]
					
					if (que_ready[0]["que_flag"] == False):
						sys.stdout.write(("que[%s] [-%d/%d]: " % (conf_opts["tag_name"], len(que_ready), conf_opts["que_limit"])) + form_info(que_ready[0],"task_info") + "\n")
						que_length += que_build(conf_opts["tag_name"], que_ready[0], secondary_obj)
						que_list[pkg_name]["que_flag"] = True
					
					que_ready.pop(0)
				
				time.sleep(wait_time)
			
			''' End of inner que loop '''
		
		''' End of outer infinite loop '''
		
		time.sleep(wait_time)

if (__name__ == "__main__"):
	main(sys.argv)
