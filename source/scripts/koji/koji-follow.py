#!/usr/bin/python

# Name: Jon Chiappetta (jonc_mailbox@yahoo.ca)
# Version: 1.0
# Date: 28/01/2013 (dd/mm/yyyy)
#
# Execution notes (*you must*):
#
# - Allow any new package names for the given build tag
# - Tag any previously completed builds into the new tag if required
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
import urllib
import urllib2

import bz2
import gzip
import koji
import rpm
import rpmUtils.miscutils
import string
import sqlite3
import xml.dom.minidom

'''
	Imported methods from the Koji source code
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

'''
	Define some error ignoring methods
'''

def check_list(list_obj, pkg_name):
	for list_item in list_obj:
		if (list_item["srpm_name"] == pkg_name):
			return 1
	return 0

def form_info(data_obj, simple_key):
	out_obj = {}
	for key_name in data_obj.keys():
		out_obj[key_name] = data_obj[key_name]
		if (key_name == simple_key):
			out_obj[key_name] = data_obj[key_name][0]
	return str(out_obj)

def delete(file_name):
	if (not file_name):
		return None
	sys.stderr.write("[info] delete: " + file_name + "\n")
	try:
		os.unlink(file_name)
	except:
		pass

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
	if (os.path.exists(file_name)):
		return 0
	
	sys.stderr.write("\t" + "[info] downloading: " + ("[%s] -> [%s]" % (url_str, file_name)) + "\n")
	
	try:
		urllib.urlretrieve(url_str, file_name)
	
	except:
		sys.stderr.write("\t" + "[error] download" + "\n")
		return 1
	
	return 0

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
			
			req_epoch = "0"
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
		url_obj = urllib2.urlopen(repodata_url)
		url_data = url_obj.read().replace("\0","").replace("\t","").replace("\r","").replace("\n","")
		url_obj.close()
		
		reg_obj = re.match("^.*['\"]([^'\"]*primary.sqlite[^'\"]*)['\"].*$", url_data, re.I)
		repo_file = reg_obj.group(1)
		package_url = ("%s/repos/%s/latest/%s/%s" % (koji_url, target_name, arch_name, repo_file))
	
	except:
		sys.stderr.write("\t" + "[error] repodata_meta: " + repodata_url + "\n")
		return ""
	
	repofile_name = os.path.basename(repo_file)
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
				db_list = db_curs.execute("SELECT packages.rpm_sourcerpm,packages.epoch,packages.version,packages.release FROM %s JOIN packages ON packages.pkgKey = %s.pkgKey WHERE %s.name = '%s';" % (cap_type, cap_type, cap_type, cap_list[x][0]))
			except:
				db_list = []
			for pkg_item in db_list:
				name_list = rpmUtils.miscutils.splitFilename(str(pkg_item[0]))
				cap_name = name_list[0]
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
	Get the latest package epoch, version, release from the specified repo database with the given package name
'''

def get_evr(pkg_name, db_name):
	final_list = {}
	
	db_conn = sqlite3.connect(db_name)
	db_curs = db_conn.cursor()
	
	try:
		db_list = db_curs.execute("SELECT rpm_sourcerpm FROM packages WHERE location_href LIKE '%%%s/%%';" % (pkg_name))
	except:
		db_list = []
	
	for pkg_item in db_list:
		(rpm_name, rpm_vers, rpm_rels, rpm_epoch, rpm_arch) = rpmUtils.miscutils.splitFilename(str(pkg_item[0]))
		if (rpm_name != pkg_name):
			continue
		if (not rpm_epoch):
			rpm_epoch = None
		final_list = {"epoch":rpm_epoch, "version":rpm_vers, "release":rpm_rels, "arch":rpm_arch}
		final_list["nvr"] = ("%s-%s-%s" % (pkg_name, final_list["version"], final_list["release"]))
	
	db_conn.close()
	
	final_list["name"] = pkg_name
	
	return final_list

'''
	Get a list of package info and urls for a given package name
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
		if (not rpm_epoch):
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
		
		item_url = ("%s/%s" % (str(pkg_item[6]), str(pkg_item[7])))
		item_info = {"name":str(pkg_item[1]), "epoch":str(pkg_item[2]), "version":str(pkg_item[3]), "release":str(pkg_item[4]), "arch":str(pkg_item[5]), "url":item_url}
		item_info["nvr"] = ("%s-%s-%s" % (item_info["name"], item_info["version"], item_info["release"]))
		final_list.append(item_info)
		
		if ((item_info["arch"] != "src") and (item_info["arch"] != "noarch")):
			arch_flag = True
	
	db_conn.close()
	
	return (arch_flag, final_list)

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
		except:
			build_info["state"] = -4
		
		if ((build_info["state"] != 0) and (build_info["state"] != 1)):
			build_info["state"] = -3
		
		try:
			build_info["task_id"] = tmp_info["task_id"]
		except:
			build_info["task_id"] = -2
	
	except:
		build_info["state"] = -2
	
	build_info["sent_nvr"] = pkg_nvr
	
	return build_info

'''
	Reorder and organize the que items into a hierarchical list based on dependencies
'''

def process_que(inpt_list):
	for que_item in inpt_list:
		tmp_list = []
		for dep_name in que_item["dep_list"]:
			if (check_list(inpt_list, dep_name) == 1):
				tmp_list.append(dep_name)
		que_item["dep_list"] = tmp_list
	
	name_list = []
	for que_item in inpt_list:
		name_list.append(que_item["srpm_name"])
	
	que_order = []
	while (1):
		tmp_list = []
		for x in range(0, len(inpt_list)):
			if (name_list[x]):
				dep_flag = 0
				for dep_name in inpt_list[x]["dep_list"]:
					if (dep_name in name_list):
						dep_flag = 1
				if (dep_flag == 0):
					tmp_list.append(inpt_list[x])
					name_list[x] = None
		if (len(tmp_list) < 1):
			break
		que_order.append(tmp_list)
	
	que_error = []
	for x in range(0, len(inpt_list)):
		if (name_list[x]):
			que_error.append(inpt_list[x])
	
	return (que_order, que_error, inpt_list)

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
		child_list = koji_obj.listTasks(opts={"parent":task_obj["id"]}, queryOpts={"limit":8})
		
		for child_task in child_list:
			if (not "id" in child_task.keys()):
				continue
			log_list = koji_obj.downloadTaskOutput(child_task["id"], "root.log")
			
			error_flag = 0
			for log_line in log_list.split("\n"):
				log_line = log_line.strip()
				if ((error_flag == 1) and ("Requires: " in log_line)):
					log_line = log_line.replace("<"," ").replace("["," ").replace("{"," ").replace("("," ")
					log_line = log_line.replace(">"," ").replace("]"," ").replace("}"," ").replace(")"," ")
					log_line = log_line.replace("="," ")
					log_line = re.sub("^.*Requires: [ ]*", "", log_line)
					log_line = re.sub(" .*$", "", log_line)
					if ((log_line) and (not log_line in final_list)):
						final_list.append(log_line)
					error_flag = 2
				elif ("Error: Package: " in log_line):
					error_flag = 1
				else:
					error_flag = 0
	
	except:
		pass
	
	return final_list

'''
	Attempt to find the original build root environment and the release version of the deps installed
'''

def last_root(koji_tag, koji_url, pkg_item):
	try:
		koji_obj = koji.ClientSession("%s/kojihub" % (koji_url))
		search_list = koji_obj.search(pkg_item["srpm_name"], "package", "glob")
	except:
		search_list = []
	
	if (len(search_list) == 1):
		last_build = None
		tag_numb = re.sub("[^0-9]", "", koji_tag)
		try:
			build_list = koji_obj.listBuilds(packageID=search_list[0]["id"])
		except:
			build_list = []
		for build_item in build_list:
			if (build_item["state"] != 1):
				continue
			rels_list = build_item["release"].split(".")
			while (len(rels_list) > 1):
				rels_list.pop(0)
			if (len(rels_list) > 0):
				rels_list[0] = re.sub("[^0-9]", "", rels_list[0])
				if (rels_list[0] == tag_numb):
					if (not last_build):
						last_build = build_item
					elif (build_item["creation_ts"] < last_build["creation_ts"]):
						last_build = build_item
		
		if (last_build):
			try:
				log_path = koji.pathinfo.build_logs(last_build)
			except:
				log_path = ""
			log_path = log_path.strip("/").split("/")
			if (len(log_path) > 2):
				log_path.pop(0) ; log_path.pop(0)
			log_path = "/".join(log_path)
			
			prev_tag = (int(tag_numb) - 1)
			
			try:
				child_list = koji_obj.getTaskChildren(last_build["task_id"])
			except:
				child_list = []
			for child_item in child_list:
				for arch_item in [child_item["arch"], child_item["label"]]:
					last_rels = []
					yum_flag = 0
					try:
						log_list = urllib.urlopen("%s/%s/%s/root.log" % (koji_url, log_path, arch_item)).readlines()
					except:
						log_list = []
					for log_line in log_list:
						log_line = log_line.replace("\t"," ").strip()
						if (yum_flag == 1):
							for dep_name in pkg_item["dep_list"]:
								regx_obj = re.match("^.* ([^ ]+)[ ]+[^ ]+[ ]+[^ ]+\.fc%d .*$" % (prev_tag), log_line)
								if ((regx_obj) and (regx_obj.group(1) == dep_name) and (not dep_name in last_rels)):
									last_rels.append(dep_name)
						if (re.match("^.*package[ ]+arch[ ]+version.*$", log_line, re.I)):
							yum_flag = 1
						if (re.match("^.*transaction[ ]+summary.*$", log_line, re.I)):
							yum_flag = 0
					if (len(last_rels) == len(pkg_item["dep_list"])):
						return True
	
	return False

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
		callback = None ; koji_obj.uploadWrapper(file_path, server_dir, callback=callback)
		server_dir = ("%s/%s" % (server_dir, os.path.basename(file_path)))
		try:
			priority = None ; koji_obj.build(server_dir, target, opts, priority=priority)
			return 1
		except:
			sys.stderr.write("\t" + "[error] build_que" + "\n")
	except:
		sys.stderr.write("\t" + "[error] build_upload" + "\n")
	
	return 0

'''
	Read a given config file and parse thru the options
'''

def conf_file(file_name, old_opts):
	file_obj = open(file_name, "r")
	
	for line_item in file_obj.readlines():
		line_item = line_item.replace("\t"," ").replace("\"","'")
		line_item = line_item.replace("[","<").replace("]",">")
		line_item = line_item.replace("(","<").replace(")",">")
		line_item = line_item.strip()
		
		if (re.match("^#[ ]*.*$", line_item)):
			continue
		
		opts_key = "" ; opts_val = ""
		
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*([0-9]+)$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = int(regx_obj.group(2))
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*'(.+)'$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = regx_obj.group(2)
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*<'(.+)'>$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = regx_obj.group(2).split("','")
		regx_obj = re.match("^([^ ]+)[ ]*=[ ]*os.path.expanduser<'(.+)'>$", line_item)
		if (regx_obj):
			opts_key = regx_obj.group(1) ; opts_val = os.path.expanduser(regx_obj.group(2))
		
		if ((opts_key != "") and (opts_val != "")):
			old_opts[opts_key] = opts_val
	
	file_obj.close()
	
	return old_opts

'''
	The main method containing the continuous primary task check/watch loop
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
	que_list = [] ; seen_list = []
	dev_null = open("/dev/null", "r+")
	
	''' ********************************
	    * Outer infinite checking loop *
	    ******************************** '''
	
	while (1):
		skip_flag = 0
		primary_repo = ""
		miss_list = []
		conf_opts = conf_file(sys.argv[1], conf_opts)
		
		#list all of the files in the pwd and delete them
		
		''' Get the build target tag for the given tag name '''
		
		if (skip_flag == 0):
			try:
				primary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["primary_url"]))
				release_info = primary_obj.getBuildTarget(conf_opts["tag_name"])
			except:
				sys.stderr.write("\t" + "[error] build_target: " + conf_opts["tag_name"] + "\n")
				skip_flag = 1
		
		''' *******************************************************************************************************
		    * Download the latest repodata files so we can process packages and convert any "BuildRequires" names *
		    ******************************************************************************************************* '''
		
		if (skip_flag == 0):
			try:
				primary_repo = ("primary.%s.db" % (release_info["build_tag_name"]))
				delete(primary_repo)
				primary_repo = get_repodata(conf_opts["primary_url"], conf_opts["primary_arch"], release_info["build_tag_name"], primary_repo)
				
				if (not os.path.exists(primary_repo)):
					sys.stderr.write("\t" + "[error] repodata_file: " + primary_repo + "\n")
					skip_flag = 1
			
			except:
				sys.stderr.write("\t" + "[error] repodata_taginfo: " + conf_opts["tag_name"] + "\n")
				skip_flag = 1
		
		''' *****************************************************************************************
		    * Get a list of the latest tagged packages for each arch and compare their ENVR numbers *
		    ***************************************************************************************** '''
		
		if (skip_flag == 0):
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
				skip_flag = 1
		
		if (skip_flag == 0):
			for primary_item in primary_tags:
				add_flag = 0
				
				if (not primary_item["name"] in secondary_dic.keys()):
					add_flag = 1
				
				else:
					primary_item = get_evr(primary_item["name"], primary_repo)
					secondary_item = secondary_dic[primary_item["name"]]
					
					if (len(primary_item.keys()) > 3):
						evr_alpha = (str(secondary_item["epoch"]), secondary_item["version"], secondary_item["release"])
						evr_beta = (str(primary_item["epoch"]), primary_item["version"], primary_item["release"])
						
						if (rpm.labelCompare(evr_alpha, evr_beta) < 0):
							add_flag = 1
				
				if (add_flag == 1):
					que_count = check_list(que_list, primary_item["name"])
					
					if (que_count == 0):
						(arch_found, task_info) = get_pkgs(primary_item["name"], primary_repo)
						miss_item = {"dep_list":[], "cap_list":[], "srpm_name":primary_item["name"], "task_info":task_info}
						
						if (arch_found == True):
							miss_list.append(miss_item)
						
						else:
							sys.stderr.write("[info]" + " noarch: " + miss_item["srpm_name"] + "\n")
							
							''' **************************************************************
								* Upload, import, tag, and skip any noarch detected packages *
								************************************************************** '''
							
							noarch_flag = 0
							
							if (noarch_flag == 0):
								if (miss_item["srpm_name"] in conf_opts["excl_list"]):
									sys.stderr.write("\t" + "[error] package_excluded" + "\n")
									noarch_flag = 1
							
							''' Download all of the noarch rpm files '''
							
							if (noarch_flag == 0):
								for pkg_item in task_info:
									rpm_file = os.path.basename(pkg_item["url"])
									if (download_file(pkg_item["url"], rpm_file) != 0):
										noarch_flag = 1
										break
									#check the integrity of the rpm file
							
							''' Login and authenticate to the Koji server '''
							
							if (noarch_flag == 0):
								try:
									secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
									secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
								except:
									sys.stderr.write("\t" + "[error] noarch_login" + "\n")
									noarch_flag = 1
							
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
										
										sys.stderr.write("\t" + "[info] import: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
										
										try:
											secondary_obj.uploadWrapper(file_path, server_dir)
											try:
												secondary_obj.importRPM(server_dir, rpm_name)
											except:
												sys.stderr.write("\t" + "[error] noarch_import" + "\n")
										except:
											sys.stderr.write("\t" + "[error] noarch_upload" + "\n")
							
							''' Tag the source rpm name '''
							
							if (noarch_flag == 0):
								for pkg_item in task_info:
									if (pkg_item["arch"] == "src"):
										sys.stderr.write("\t" + "[info] tag: " + ("[%s] <- [%s]" % (conf_opts["tag_name"], pkg_item["nvr"])) + "\n")
										
										try:
											secondary_obj.tagBuild(conf_opts["tag_name"], pkg_item["nvr"])
										except:
											sys.stderr.write("\t" + "[error] noarch_tag" + "\n")
		
		#sys.exit(0)
		
		''' **********************************************
		    * Inner processing loop for missing packages *
		    ********************************************** '''
		
		x = 0
		
		while (x < len(miss_list)):
			sys.stderr.write("[info] processing: " + ("[%d/%d] " % (x + 1, len(miss_list))) + form_info(miss_list[x],"task_info") + "\n")
			
			skip_flag = 0
			task_info = miss_list[x]["task_info"]
			
			if (skip_flag == 0):
				if (miss_list[x]["srpm_name"] in conf_opts["excl_list"]):
					sys.stderr.write("\t" + "[error] package_excluded" + "\n")
					skip_flag = 1
			
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
						
						srpm_out = subprocess.check_output(["/usr/bin/rpmbuild", "-bs", "--target", conf_opts["target_arch"], spec_file], stderr=subprocess.STDOUT)
						
						for out_line in srpm_out.split("\n"):
							out_line = out_line.strip()
							if (out_line[:7].lower() == "wrote: "):
								srpm_file = out_line[7:]
						
						sys.stderr.write("\t" + "[info] rpm_build: " + ("([%s] [%s]) -> [%s]" % (conf_opts["target_arch"], spec_file, srpm_file)) + "\n")
						
						rpm_info = rpm_header(srpm_file, None)
						miss_list[x]["cap_list"] = rpm_info[1]
					
					except:
						sys.stderr.write("\t" + "[error] spec_file: " + srpm_file + "\n")
						skip_flag = 1
				
				else:
					sys.stderr.write("\t" + "[error] rpmdev_install: " + srpm_file + "\n")
					skip_flag = 1
			
			''' *******************************************************************************************************
			    * Translate any capability or binary package requires to a source package name and append it as a dep *
			    ******************************************************************************************************* '''
			
			if (skip_flag == 0):
				req_list = map_cap(miss_list[x]["cap_list"], primary_repo)
				miss_list[x]["cap_list"] = []
				
				for req_item in req_list:
					miss_list[x]["dep_list"].append(req_item[0])
				
				sys.stderr.write("\t" + "[info] dep_list: " + str(miss_list[x]["dep_list"]) + "\n")
			
			''' ********************************************************************************
			    * Append this processed task to the que list if needed and check the next task *
			    ******************************************************************************** '''
			
			if (skip_flag == 0):
				que_flag = check_list(que_list, miss_list[x]["srpm_name"])
				if (que_flag == 0):
					secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
					miss_list[x]["que_state"] = koji_state(task_info[0]["nvr"], secondary_obj)
					sys.stderr.write("\t" + "[info] build_info: " + str(miss_list[x]["que_state"]) + "\n")
					if ((miss_list[x]["que_state"]["state"] != 0) and (miss_list[x]["que_state"]["state"] != 1)):
						que_list.append(miss_list[x])
			
			x += 1
		
		#sys.exit(0)
		
		''' ****************************************************************
		    * Inner que'ing loop for the first level of processed packages *
		    **************************************************************** '''
		
		sys.stdout.write("[info] Starting que loop..." + "\n")
		
		wait_list = []
		(que_order, que_error, que_list) = process_que(que_list)
		if (len(que_order) > 0):
			for que_item in que_order[0]:
				wait_list.append(que_item)
		
		while (1):
			sys.stdout.write("\n")
			sys.stdout.write("#############" + "\n")
			sys.stdout.write("# Que Round #" + "\n")
			sys.stdout.write("#############" + "\n\n")
			
			conf_opts = conf_file(sys.argv[1], conf_opts)
			
			''' Login and authenticate to the Koji server '''
			
			try:
				secondary_obj = koji.ClientSession("%s/kojihub" % (conf_opts["secondary_url"]))
				secondary_obj.ssl_login(conf_opts["client_cert"], conf_opts["server_cert"], conf_opts["server_cert"])
			except:
				sys.stderr.write("\t" + "[error] build_login" + "\n")
				time.sleep(wait_time)
				continue
			
			''' Get a count of our active tasks '''
			
			try:
				secondary_tasks = secondary_obj.listTasks(opts={"state":[0,1], "method":"build"}, queryOpts={"limit":900})
				#list my tasks only
				que_length = len(secondary_tasks)
				if (que_length >= conf_opts["que_limit"]):
					raise NameError("TooManyTasks")
			except:
				sys.stderr.write("\t" + "[error] task_list/que_max: " + ("[%d/%d]" % (que_length, conf_opts["que_limit"])) + "\n")
				time.sleep(wait_time)
				continue
			
			''' Que any new packages now '''
			
			if (len(wait_list) < 1):
				if (len(que_error) < 1):
					break
				while ((len(que_error) > 0) and (len(wait_list) < conf_opts["que_limit"])):
					if (last_root(conf_opts["tag_name"], conf_opts["primary_url"], que_error[0]) == True):
						wait_list.append(que_error[0])
					que_error.pop(0)
			
			while ((len(wait_list) > 0) and (que_length < conf_opts["que_limit"])):
				pkg_envr = wait_list[0]["task_info"][0]["nvr"]
				if (not pkg_envr in seen_list):
					sys.stdout.write(("que [%s] [%d/%d]: " % (conf_opts["tag_name"], que_length + 1, conf_opts["que_limit"])) + form_info(wait_list[0],"task_info") + "\n")
					que_length += que_build(conf_opts["tag_name"], wait_list[0], secondary_obj)
					seen_list.append(pkg_envr)
				wait_list.pop(0)
			
			#sys.exit(0)
			
			time.sleep(wait_time)
		
		#error packages are ones that we sent for build but failed (check build states once only & wait for those currently building)
		
		''' End of infinite outer loop '''
		
		#sys.exit(0)
		
		sys.stdout.write("[info] Exited que loop..." + "\n")
		time.sleep(wait_time)

if (__name__ == "__main__"):
	main(sys.argv)
