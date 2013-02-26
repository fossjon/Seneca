#!/usr/bin/python

# Version: 1.8
# Date: 26/02/2013 (dd/mm/yyyy)
# Name: Jon Chiappetta (jonc_mailbox@yahoo.ca)
#
# Execution notes (*you must*):
#
# - Allow and add any new package names to the given build tag
# - Resolve any circular dependency package issues

'''
	Define the needed imports
'''

import ast
import os
import random
import re
import string
import subprocess
import sys
import time

import bz2
import gzip
import koji
import rpm
import rpmUtils.miscutils
import sqlite3
import urllib2
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
	Delete the given filename if the file exists
'''

def delete(file_name):
	if (not file_name):
		return 1
	sys.stderr.write("\t" + "[info] file_delete: " + file_name + "\n")
	try:
		os.unlink(file_name)
	except:
		return 1
	return 0

'''
	Read a given config file and parse thru the pre-set options
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

def local_db(pkg_list, db_mode, post_fix=""):
	if (db_mode == 0):
		delete(".kf-state.db.tmp%s" % (post_fix))
	
	elif (db_mode == 1):
		db_conn = sqlite3.connect(".kf-state.db.tmp%s" % (post_fix))
		db_curs = db_conn.cursor()
		
		try:
			db_curs.execute("CREATE TABLE packages (pkg_name text, pkg_info text);")
		except:
			pass
		
		for pkg_item in pkg_list:
			try:
				db_curs.execute("INSERT INTO packages VALUES ('%s', \"%s\");" % (pkg_item["name"], str(pkg_item)))
			except:
				pass
		
		db_conn.commit()
		db_conn.close()
	
	elif (db_mode == 2):
		delete(".kf-state.db%s" % (post_fix))
		
		try:
			os.rename(".kf-state.db.tmp%s" % (post_fix), ".kf-state.db%s" % (post_fix))
		except:
			pass
	
	elif (db_mode == 3):
		db_list = []
		
		db_conn = sqlite3.connect(".kf-state.db%s" % (post_fix))
		db_curs = db_conn.cursor()
		
		try:
			for db_row in db_curs.execute("SELECT * FROM packages;"):
				db_list.append(str(db_row[1]))
		except:
			pass
		
		db_conn.commit()
		db_conn.close()
		
		return db_list
	
	elif (db_mode == 4):
		delete(".kf-state.db%s" % (post_fix))

''' **********************************
    * General script related methods *
    ********************************** '''

'''
	Download a given url link to a specified filename
'''

def download_file(url_str, file_name):
	if (file_name):
		if (os.path.exists(file_name)):
			return 0
	
	sys.stderr.write("\t" + "[info] file_download: " + ("[%s] -> [%s]" % (url_str, file_name)) + "\n")
	
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
		sys.stderr.write("\t" + "[error] download_file" + "\n")
		return 1
	
	return 0

'''
	Rebuild a given source rpm file with the specified spec file changes
'''

def rebuild_srpm(srpm_file, rels_info):
	dev_null = open("/dev/null", "r+")
	
	subprocess.call(["/usr/bin/rpmdev-wipetree"], stdout=dev_null, stderr=subprocess.STDOUT)
	
	if (subprocess.call(["/bin/rpm", "-i", srpm_file], stdout=dev_null, stderr=subprocess.STDOUT) != 0):
		sys.stderr.write("\t" + "[error] rpm_install: " + srpm_file + "\n")
		dev_null.close()
		return ""
	
	try:
		spec_path = os.path.expanduser("~/rpmbuild/SPECS")
		spec_list = os.listdir(spec_path)
		spec_file = (spec_path + "/" + spec_list[0])
	except:
		sys.stderr.write("\t" + "[error] spec_find: " + srpm_file + "\n")
		dev_null.close()
		return ""
	
	try:
		file_obj = open(spec_file, "r")
		line_list = file_obj.readlines()
		file_obj.close()
	except:
		sys.stderr.write("\t" + "[error] spec_read: " + spec_file + "\n")
		dev_null.close()
		return ""
	
	try:
		rels_flag = 0
		file_obj = open(spec_file, "w")
		for line_item in line_list:
			tmp_line = line_item.replace("\t"," ").strip()
			regx_obj = re.match("^Release: .*$", tmp_line, re.I)
			if ((regx_obj) and (rels_flag == 0)):
				line_item = ("Release: %s.%skf\n" % (rels_info, time.strftime("%y%m%d%H%M")))
				rels_flag = 1
			file_obj.write(line_item)
		file_obj.close()
	except:
		sys.stderr.write("\t" + "[error] spec_write: " + spec_file + "\n")
		dev_null.close()
		return ""
	
	try:
		srpm_out = subprocess.check_output(["/usr/bin/rpmbuild", "-bs", spec_file], stderr=subprocess.STDOUT)
		for out_line in srpm_out.split("\n"):
			out_line = out_line.replace("\t"," ").strip()
			regx_obj = re.match("^wrote: [ ]*(.*)$", out_line, re.I)
			if (regx_obj):
				dev_null.close()
				return regx_obj.group(1)
	except:
		sys.stderr.write("\t" + "[error] rpm_build: " + spec_file + "\n")
		dev_null.close()
		return ""
	
	dev_null.close()
	return ""

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
				build_info["state"] = -9
		except:
			build_info["state"] = -3
		
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
	Insert a given info item in sorted order based on a given key-name value into a pre-sorted list of items
'''

def sorted_insert(insert_obj, sorted_key, input_list):
	tmp_list = []
	insert_flag = 0
	
	for input_item in input_list:
		if ((insert_flag == 0) and (insert_obj[sorted_key] < input_item[sorted_key])):
			tmp_list.append(insert_obj)
			insert_flag = 1
		tmp_list.append(input_item)
	
	if (insert_flag == 0):
		tmp_list.append(insert_obj)
	
	return tmp_list

'''
	Attempt to find all of the successful build attempts for a given package and tag name
'''

def build_history(pkg_name, koji_tag, koji_obj):
	history_list = []
	
	try:
		search_list = koji_obj.search(pkg_name, "package", "glob")
	except:
		search_list = []
	
	if (len(search_list) == 1):
		try:
			build_list = koji_obj.listBuilds(packageID=search_list[0]["id"])
		except:
			build_list = []
		
		for build_item in build_list:
			if (build_item["state"] != 1):
				continue
			tag_flag = 0
			
			tag_numb = re.sub("[^0-9]", "", koji_tag)
			regx_end = re.match("^.*\.fc%s$" % (tag_numb), build_item["release"], re.I)
			regx_mid = re.match("^.*\.fc%s\..*$" % (tag_numb), build_item["release"], re.I)
			if (regx_end or regx_mid):
				tag_flag = 1
			
			if (tag_flag != 1):
				continue
			history_list.append(build_item)
		
		if (len(history_list) < 1):
			for build_item in build_list:
				if (build_item["state"] != 1):
					continue
				tag_flag = 0
				
				try:
					tag_list = koji_obj.listTags(build_item["nvr"])
				except:
					tag_list = []
				for tag_item in tag_list:
					if (tag_item["name"] == koji_tag):
						tag_flag = 1
				
				if (tag_flag != 1):
					continue
				history_list.append(build_item)
	
	return history_list

'''
	Check to see if the given build item is a noarch package
'''

def noarch_check(build_id, koji_obj):
	arch_flag = 0
	try:
		rpm_list = koji_obj.listRPMs(buildID=build_id)
	except:
		arch_flag = 1
		rpm_list = []
	for rpm_item in rpm_list:
		if ((rpm_item["arch"] != "src") and (rpm_item["arch"] != "noarch")):
			arch_flag = 1
	return (arch_flag, rpm_list)

'''
	Upload, import, tag, and skip any noarch detected packages
'''

def import_noarch(noarch_list, src_koji, src_url, dst_koji, dst_tag):
	dev_null = open("/dev/null", "r+")
	path_info = koji.PathInfo(topdir=src_url) ; srpm_info = None
	
	for pkg_item in noarch_list:
		if (pkg_item["arch"] == "src"):
			try:
				srpm_info = src_koji.getBuild(pkg_item["nvr"])
			except:
				srpm_info = None
	
	if (srpm_info == None):
		sys.stderr.write("\t" + "[error] noarch_srpm" + str(noarch_list) + "\n")
		return 1
	
	sys.stderr.write("\t" + "[info]" + " import_noarch: " + str(srpm_info) + "\n")
	
	''' Download all of the noarch rpm files '''
	
	down_list = []
	
	for pkg_item in noarch_list:
		rpm_url = (path_info.build(build_info) + "/" + path_info.rpm(pkg_item))
		rpm_file = os.path.basename(rpm_url)
		delete(rpm_file)
		if (download_file(rpm_url, rpm_file) != 0):
			return 1
		if (subprocess.call(["/bin/rpm", "-K", rpm_file], stdout=dev_null, stderr=subprocess.STDOUT) != 0):
			sys.stderr.write("\t\t" + "[error] noarch_verify: " + ("[%s] -> [%s]" % (rpm_url, rpm_file)) + "\n")
			return 1
		down_list.append([pkg_item, rpm_url, rpm_file])
	
	''' Upload and import the related rpm files '''
	
	for y in range(0, 2):
		for down_item in down_list:
			pkg_item = down_item[0]
			
			if ((y == 0) and (pkg_item["arch"] != "src")):
				continue
			if ((y != 0) and (pkg_item["arch"] == "src")):
				continue
			
			pres_dir = os.getcwd()
			rpm_name = down_item[2]
			file_path = ("%s/%s" % (pres_dir, rpm_name))
			server_dir = _unique_path("cli-import")
			
			#sys.stderr.write("\t" + "[info] file_import: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
			
			try:
				dst_koji.uploadWrapper(file_path, server_dir)
				try:
					dst_koji.importRPM(server_dir, rpm_name)
				except:
					sys.stderr.write("\t\t" + "[error] noarch_import: " + ("[%s] -> [%s]" % (server_dir, rpm_name)) + "\n")
			except:
				sys.stderr.write("\t\t" + "[error] noarch_upload: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
	
	''' Tag the source rpm name '''
	
	for pkg_item in noarch_list:
		if (pkg_item["arch"] == "src"):
			#sys.stderr.write("\t" + "[info] pkg_tag: " + ("[%s] <- [%s]" % (dst_tag, pkg_item["nvr"])) + "\n")
			
			try:
				dst_koji.tagBuild(dst_tag, pkg_item["nvr"])
			except:
				sys.stderr.write("\t\t" + "[error] noarch_tag: " + ("[%s] <- [%s]" % (dst_tag, pkg_item["nvr"])) + "\n")
	
	dev_null.close()
	return 0

'''
	Que a package to be built
'''

def que_build(target, file_path, koji_obj):
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
			sys.stderr.write("\t\t" + "[error] build_que" + "\n")
	except:
		sys.stderr.write("\t\t" + "[error] build_upload" + "\n")
	
	return 0

''' *****************************
    * Primary execution methods *
    ***************************** '''

'''
	The main method containing the continuous package version check/watch loop
'''

def main(args):
	wait_time = (2 * 60)
	conf_opts = {}
	
	while (1):
		conf_opts = conf_file(args[1], conf_opts)
		
		''' List the latest tagged packages for this given tag name '''
		
		try:
			primary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["primary_url"]))
			primary_tags = primary_obj.listTagged(conf_opts["tag_name"], inherit=False, latest=True)
			
			secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
			secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
		
		except:
			sys.stderr.write("[error] latest_tagged" + "\n")
			time.sleep(wait_time)
			continue
		
		''' Process the list of tagged packages and/or previous build history for each package '''
		
		primary_len = len(primary_tags)
		child_num = 32 ; child_len = ((primary_len / child_num) + 2) ; child_list = []
		x = 0 ; l = 0
		
		for i in range(0, child_num):
			x = l ; l += child_len
			pid_num = os.fork()
			primary_builds = []
			
			if (pid_num == 0):
				for y in range(x, l):
					if (y >= primary_len):
						continue
					primary_item = primary_tags[y]
					
					sys.stderr.write("[info] primary_tag: " + ("[%d/%d/%d]: %s" % (x, y, l, primary_item["name"])) + "\n")
					
					(arch_pkg, pkg_list) = noarch_check(primary_item["build_id"], primary_obj)
					if (arch_pkg == 0):
						import_noarch(pkg_list, primary_obj, conf_opts["primary_url"], secondary_obj, conf_opts["tag_name"])
						continue
					
					if (conf_opts["check_tag"] == "all"):
						build_list = build_history(primary_item["name"], conf_opts["tag_name"], primary_obj)
						for build_item in build_list:
							primary_builds.append(build_item)
					elif (conf_opts["check_tag"] == "latest"):
						primary_builds.append(primary_item)
				
				if ((conf_opts["check_tag"] == "all") or (conf_opts["check_tag"] == "latest")):
					local_db(None, 0, post_fix=str(i))
					local_db(primary_builds, 1, post_fix=str(i))
					local_db(None, 2, post_fix=str(i))
				
				sys.exit(0)
			
			else:
				child_list.append(pid_num)
		
		''' Merge the above database result files from the above processes into one database file '''
		
		if ((conf_opts["check_tag"] == "all") or (conf_opts["check_tag"] == "latest")):
			local_db(None, 0, post_fix="")
			
			for i in range(0, child_num):
				os.waitpid(child_list[i], 0)
				db_list = []
				for db_str in local_db(None, 3, post_fix=str(i)):
					db_obj = ast.literal_eval(db_str)
					db_list.append(db_obj)
				local_db(db_list, 1, post_fix="")
				local_db(None, 4, post_fix=str(i))
			
			local_db(None, 2, post_fix="")
		
		''' Read from the database and sort the potential missing builds by creation time '''
		
		pkg_list = []
		for db_str in local_db(None, 3, post_fix=""):
			db_obj = ast.literal_eval(db_str)
			pkg_list = sorted_insert(db_obj, "creation_ts", pkg_list)
		
		''' Loop thru the potential builds and que the packages marked as ready '''
		
		x = 0 ; l = len(pkg_list)
		for pkg_item in pkg_list:
			x += 1
			conf_opts = conf_file(args[1], conf_opts)
			
			sys.stdout.write("[info] pkg_process: " + ("[%d/%d]: %s" % (x, l, str(pkg_item))) + "\n")
			
			while (1):
				try:
					secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
					secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
				except:
					sys.stderr.write("[error] que_login" + "\n")
					secondary_obj = None
				if (secondary_obj != None):
					break
				time.sleep(wait_time)
			
			''' Skip any packages that have been requested to be excluded '''
			
			if (pkg_item["name"] in conf_opts["excl_list"]):
				sys.stdout.write("\t" + "[info] pkg_excluded" + "\n")
				continue
			
			''' Check the state build state of the current package '''
			
			state_info = koji_state(pkg_item["nvr"], secondary_obj)
			if ((state_info["state"] > -1) and (conf_opts["retry_build"] != "all")):
				sys.stdout.write("\t" + "[info] locked_state: " + ("%s" % (str(state_info))) + "\n")
				continue
			if ((state_info["state"] < -5) and (conf_opts["retry_build"] != "failed") and (conf_opts["retry_build"] != "all")):
				sys.stdout.write("\t" + "[info] failed_state: " + ("%s" % (str(state_info))) + "\n")
				continue
			
			''' Download the given source rpm file and change its release tag if requested '''
			
			srpm_url = ("%s/packages/%s/%s/%s/src/%s.src.rpm" % (conf_opts["primary_url"], pkg_item["name"], pkg_item["version"], pkg_item["release"], pkg_item["nvr"]))
			srpm_name = os.path.basename(srpm_url)
			delete(srpm_name)
			if (download_file(srpm_url, srpm_name) != 0):
				continue
			if ((state_info["state"] > -1) and (conf_opts["retry_build"] == "all")):
				srpm_name = rebuild_srpm(srpm_name, pkg_item["release"])
			
			''' Check to make sure that the given rpm file path exists '''
			
			if (not os.path.exists(srpm_name)):
				sys.stdout.write("\t" + "[error] path_notexists" + "\n")
				continue
			
			''' Get a count of our active tasks '''
			
			while (1):
				try:
					user_info = secondary_obj.getLoggedInUser()
					task_list = secondary_obj.listTasks(opts={"state":[0,1], "method":"build", "owner":user_info["id"]}, queryOpts={"limit":900})
					task_len = len(task_list)
				except:
					sys.stderr.write("[error] que_listtasks" + "\n")
					task_len = -1
				if ((-1 < task_len) and (task_len < conf_opts["que_limit"])):
					break
				time.sleep(wait_time)
			
			''' Que the request source rpm file '''
			
			que_build(conf_opts["tag_name"], srpm_name, secondary_obj)
		
		sys.exit(0)
		time.sleep(wait_time)

if (__name__ == "__main__"):
	main(sys.argv)

