#!/usr/bin/python
# Note: This script cannot resolve circular dependency issues

'''while (1):
		try:
			secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
			secondary_tasks = secondary_obj.listTasks(opts={"state":[0,1], "method":"newRepo"}, queryOpts={"limit":900})
			if (len(secondary_tasks) > 0):
				raise NameError("RepoTaskWait")
		except:
			sys.stderr.write("\t" + "[error] repo_tasks: " + ("[%d]" % (len(secondary_tasks))) + "\n")
			time.sleep(3 * 60)
			continue
		break'''

'''
	Define the needed imports
'''

import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib
import urllib2

from xml.dom.minidom import parseString

import bz2
import gzip
import koji
import rpm
import rpmUtils.miscutils
import sqlite3

'''
	Imported from the Koji source code
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
	sys.stderr.write("\t" + "[info] downloading: " + ("[%s] -> [%s]" % (url_str, file_name)) + "\n")
	
	if (os.path.exists(file_name)):
		return 0
	
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
		primary_url = ("%s/repos/%s/latest/%s/%s" % (koji_url, target_name, arch_name, repo_file))
	
	except:
		sys.stderr.write("\t" + "[error] repodata_meta: " + repodata_url + "\n")
		return ""
	
	repofile_name = os.path.basename(repo_file)
	if (download_file(primary_url, repofile_name) != 0):
		sys.stderr.write("\t" + "[error] repodata_db: " + primary_url + "\n")
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
	final_list = []
	
	db_conn = sqlite3.connect(db_name)
	db_curs = db_conn.cursor()
	
	try:
		db_list = db_curs.execute("SELECT packages.epoch,packages.version,packages.release FROM packages WHERE packages.name = '%s';" % (pkg_name))
	except:
		db_list = []
	
	for pkg_item in db_list:
		final_list = [pkg_name, "EQ", str(pkg_item[0]), str(pkg_item[1]), str(pkg_item[2])]
	
	db_conn.close()
	
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
		db_list = db_curs.execute("SELECT name,epoch,version,release,arch,location_base,location_href,rpm_sourcerpm FROM packages WHERE location_href LIKE '%s/%%';" % (pkg_name))
	except:
		db_list = []
	
	for pkg_item in db_list:
		item_url = ("%s/%s" % (str(pkg_item[5]), str(pkg_item[6])))
		item_info = {"name":str(pkg_item[0]), "epoch":str(pkg_item[1]), "version":str(pkg_item[2]), "release":str(pkg_item[3]), "arch":str(pkg_item[4]), "url":item_url}
		item_info["nvr"] = ("%s-%s-%s" % (item_info["name"], item_info["version"], item_info["release"]))
		
		if (len(final_list) < 1):
			final_list.append({})
			for item_key in item_info.keys():
				final_list[0][item_key] = item_info[item_key]
			final_list[0]["name"] = pkg_name
			final_list[0]["arch"] = "src"
			final_list[0]["url"] = ("%s/%s/%s/%s/%s/%s" % (str(pkg_item[5]), final_list[0]["name"], item_info["version"], item_info["release"], final_list[0]["arch"], str(pkg_item[7])))
			final_list[0]["nvr"] = ("%s-%s-%s" % (final_list[0]["name"], final_list[0]["version"], final_list[0]["release"]))
		
		if ((item_info["arch"] != "src") and (item_info["arch"] != "noarch")):
			arch_flag = True
		
		final_list.append(item_info)
	
	db_conn.close()
	
	return [arch_flag, final_list]

'''
	Reorder and organize the que items into a hierarchical list based on dependencies
'''

def process_que(inpt_list):
	que_tmp = inpt_list[:] ; name_list = []
	for x in range(0, len(que_tmp)):
		name_list.append(que_tmp[x]["srpm_name"])
	
	que_order = [] ; que_error = []
	while (1):
		tmp_list = []
		for x in range(0, len(que_tmp)):
			if ((que_tmp[x]) and (que_tmp[x]["que_state"] >= 0)):
				dep_flag = 0
				for dep_name in que_tmp[x]["dep_list"]:
					if (dep_name in name_list):
						dep_flag = 1
				if (dep_flag == 0):
					tmp_list.append(que_tmp[x])
					que_tmp[x] = None ; name_list[x] = None
		if (len(tmp_list) < 1):
			break
		que_order.append(tmp_list)
	
	for que_item in que_tmp:
		if (que_item):
			que_error.append(que_item)
	
	return (que_order, que_error)

'''
	Get the latest build state for a given package name
'''

def koji_state(pkg_name, repo_file, koji_obj):
	build_info = {"state":-1}
	primary_evr = get_evr(pkg_name, repo_file)
	
	# koji.BUILD_STATES['s'] = {0:'BUILDING',1:'COMPLETE',2:'DELETED',3:'FAILED',4:'CANCELED'}
	
	if (not primary_evr):
		return {}
	
	try:
		build_info = koji_obj.getBuild("%s-%s-%s" % (primary_evr[0], primary_evr[3], primary_evr[4]))
	except:
		build_info = {"state":-2}
	
	return build_info

'''
	Check a list of items for a specific package name
'''

def check_list(list_obj, pkg_name):
	for list_item in list_obj:
		if (list_item["srpm_name"] == pkg_name):
			return 1
	return 0

'''
	The main method containing the continuous primary task check/watch loop
'''

def main(args):
	''' Define the commonly referenced variables '''
	
	#primary_url = "http://koji.fedoraproject.org"
	#primary_arch = "x86_64"
	#secondary_url = "http://arm.koji.fedoraproject.org"
	#secondary_arch = "armhfp"
	
	primary_url = "http://arm.koji.fedoraproject.org"
	primary_arch = "armhfp"
	secondary_url = "http://japan.proximity.on.ca"
	secondary_arch = "armv6hl"
	
	client_cert = os.path.expanduser("~/.fedora.cert")
	server_cert = os.path.expanduser("~/.fedora-server-ca.cert")
	
	tag_name = sys.argv[1]
	que_limit = int(sys.argv[2])
	rpmb_arch = "arm"
	que_list = []
	dev_null = open("/dev/null", "r+")
	
	try:
		excl_list = sys.argv[3].split(",")
	except:
		excl_list = []
	
	#read and initialize last saved state
	
	''' Start an infinite loop to monitor and check for changes '''
	
	while (1):
		skip_flag = 0
		primary_repo = ""
		miss_list = []
		
		#read config file for changes
		#detect and wait for repo-tasks with this release-tag type
		
		''' Get the build target tag for the given tag name '''
		
		if (skip_flag == 0):
			try:
				primary_obj = koji.ClientSession("%s/kojihub" % (primary_url))
				release_info = primary_obj.getBuildTarget(tag_name)
			except:
				sys.stderr.write("\t" + "[error] build_target: " + tag_name + "\n")
				skip_flag = 1
		
		''' *******************************************************************************************************
		    * Download the latest repodata files so we can process packages and convert any "BuildRequires" names *
		    ******************************************************************************************************* '''
		
		if (skip_flag == 0):
			try:
				primary_repo = ("primary.%s.db" % (release_info["build_tag_name"]))
				delete(primary_repo)
				primary_repo = get_repodata(primary_url, primary_arch, release_info["build_tag_name"], primary_repo)
				
				if (not os.path.exists(primary_repo)):
					sys.stderr.write("\t" + "[error] repodata_file: " + primary_repo + "\n")
					skip_flag = 1
			
			except:
				sys.stderr.write("\t" + "[error] repodata_taginfo: " + tag_name + "\n")
				skip_flag = 1
		
		''' *****************************************************************************************
		    * Get a list of the latest tagged packages for each arch and compare their ENVR numbers *
		    ***************************************************************************************** '''
		
		if (skip_flag == 0):
			try:
				sys.stderr.write("[info] latest_tagged: " + tag_name + "\n")
				
				primary_obj = koji.ClientSession("%s/kojihub" % (primary_url))
				primary_tags = primary_obj.listTagged(tag_name, inherit=False, latest=True)
				
				secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
				secondary_tags = secondary_obj.listTagged(tag_name, inherit=False, latest=True)
				
				secondary_dic = {}
				for secondary_item in secondary_tags:
					secondary_dic[secondary_item["name"]] = secondary_item
				
				for primary_item in primary_tags:
					add_flag = 0
					
					if (not primary_item["name"] in secondary_dic.keys()):
						add_flag = 1
					
					else:
						secondary_item = secondary_dic[primary_item["name"]]
						
						primary_evr = [primary_item["name"], "EQ", str(primary_item["epoch"]), primary_item["version"], primary_item["release"]]
						secondary_evr = [secondary_item["name"], "EQ", str(secondary_item["epoch"]), secondary_item["version"], secondary_item["release"]]
						
						evr_alpha = (str(secondary_item["epoch"]), secondary_item["version"], secondary_item["release"])
						evr_beta = (str(primary_item["epoch"]), primary_item["version"], primary_item["release"])
						
						if (rpm.labelCompare(evr_alpha, evr_beta) < 0):
							add_flag = 1
					
					if (add_flag == 1):
						que_count = check_list(que_list, primary_item["name"])
						
						if (que_count == 0):
							task_obj = get_pkgs(primary_item["name"], primary_repo)
							miss_item = {"dep_list":[], "cap_list":[], "srpm_name":primary_item["name"], "task_info":task_obj[1], "arch_flag":task_obj[0]}
							miss_list.append(miss_item)
			
			except:
				sys.stderr.write("\t" + "[error] latest_tagged" + "\n")
				skip_flag = 1
		
		#sys.exit(0)
		
		''' Loop thru the current list of out dated packages and analyze them '''
		
		x = 0
		
		while (x < len(miss_list)):
			sys.stderr.write("[info]" + (" [%d/%d]" % (x + 1, len(miss_list))) + " processing: " + str(miss_list[x]) + "\n")
			
			skip_flag = 0
			task_info = miss_list[x]["task_info"]
			
			if (miss_list[x]["srpm_name"] in excl_list):
				sys.stderr.write("\t" + "[info] package_excluded" + "\n")
				skip_flag = 1
			
			''' **************************************************************
			    * Upload, import, tag, and skip any noarch detected packages *
			    ************************************************************** '''
			
			if (skip_flag == 0):
				if (miss_list[x]["arch_flag"] == False):
					for pkg_item in task_info:
						rpm_file = os.path.basename(pkg_item["url"])
						if (download_file(pkg_item["url"], rpm_file) != 0):
							skip_flag = 1
							break
						#check the rpm file integrity
					
					if (skip_flag == 0):
						try:
							secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
							secondary_obj.ssl_login(client_cert, server_cert, server_cert)
						except:
							sys.stderr.write("\t" + "[error] noarch_login" + "\n")
							skip_flag = 1
					
					if (skip_flag == 0):
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
								
								sys.stderr.write("\t" + "[info] noarch_import: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
								
								try:
									secondary_obj.uploadWrapper(file_path, server_dir)
									try:
										secondary_obj.importRPM(server_dir, rpm_name)
									except:
										sys.stderr.write("\t" + "[error] noarch_import" + "\n")
								except:
									sys.stderr.write("\t" + "[error] noarch_upload" + "\n")
					
					if (skip_flag == 0):
						for pkg_item in task_info:
							if (pkg_item["arch"] == "src"):
								sys.stderr.write("\t" + "[info] noarch_tag: " + ("[%s] <- [%s]" % (tag_name, pkg_item["nvr"])) + "\n")
								
								try:
									secondary_obj.tagBuild(tag_name, pkg_item["nvr"])
								except:
									sys.stderr.write("\t" + "[error] noarch_tag" + "\n")
					
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
						
						srpm_out = subprocess.check_output(["/usr/bin/rpmbuild", "-bs", "--target", rpmb_arch, spec_file], stderr=subprocess.STDOUT)
						
						for out_line in srpm_out.split("\n"):
							out_line = out_line.strip()
							if (out_line[:7].lower() == "wrote: "):
								srpm_file = out_line[7:]
						
						sys.stderr.write("\t" + "[info] rpm_build: " + ("([%s] [%s]) -> [%s]" % (rpmb_arch, spec_file, srpm_file)) + "\n")
						
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
					for miss_item in miss_list:
						if (miss_item["srpm_name"] == req_item[0]):
							miss_list[x]["dep_list"].append(req_item[0])
			
			''' ********************************************************************************
			    * Append this processed task to the que list if needed and check the next task *
			    ******************************************************************************** '''
			
			if (skip_flag == 0):
				que_flag = check_list(que_list, miss_list[x]["srpm_name"])
				if (que_flag == 0):
					secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
					build_info = koji_state(miss_list[x]["srpm_name"], primary_repo, secondary_obj)
					if (build_info):
						miss_list[x]["que_state"] = build_info["state"]
						que_list.append(miss_list[x])
			
			x += 1
		
		''' *********************************************************
		    * Display and que the first level of processed packages *
		    ********************************************************* '''
		
		# koji.TASK_STATES['s'] = {0:'FREE',1:'OPEN',2:'CLOSED',3:'CANCELED',4:'ASSIGNED',5:'FAILED'}
		
		wait_time = (3 * 60)
		while (1):
			(que_order, que_error) = process_que(que_list)
			que_length = 0
			
			if (len(que_order) < 1):
				break
			
			try:
				secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
				secondary_tasks = secondary_obj.listTasks(opts={"state":[0,1], "method":"build"}, queryOpts={"limit":900})
				que_length = len(secondary_tasks)
				if (que_length >= que_limit):
					raise NameError("TooManyTasks")
			except:
				sys.stderr.write("\t" + "[error] task_list/que_limit: " + ("[%d/%d]" % (que_length, que_limit)) + "\n")
				time.sleep(wait_time)
				continue
			
			sys.stdout.write("*************" + "\n")
			sys.stdout.write("* Que Round *" + "\n")
			sys.stdout.write("*************" + "\n\n")
			
			try:
				secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
				secondary_obj.ssl_login(client_cert, server_cert, server_cert)
			except:
				sys.stderr.write("\t" + "[error] build_login" + "\n")
				time.sleep(wait_time)
				continue
			
			que_level = 0
			for list_item in que_order:
				for que_item in list_item:
					sys.stdout.write(("que[%d] [%d/%d]: " % (que_level, que_length, que_limit)) + str(que_item) + "\n")
					if ((que_level == 0) and (que_length < que_limit)):
						pres_dir = os.getcwd()
						rpm_name = os.path.basename(que_item["task_info"][0]["url"])
						file_path = ("%s/%s" % (pres_dir, rpm_name))
						server_dir = _unique_path("cli-build")
						
						target = tag_name
						opts = {}
						
						sys.stdout.write("\t" + "[info] que_build: " + ("[%s] -> [%s]" % (file_path, server_dir)) + "\n")
						
						try:
							callback = None ; secondary_obj.uploadWrapper(file_path, server_dir, callback=callback)
							server_dir = ("%s/%s" % (server_dir, os.path.basename(file_path)))
							try:
								priority = None ; secondary_obj.build(server_dir, target, opts, priority=priority)
								que_length += 1
							except:
								sys.stderr.write("\t" + "[error] build_que" + "\n")
						except:
							sys.stderr.write("\t" + "[error] build_upload" + "\n")
				
				que_level += 1
			
			for error_item in que_error:
				sys.stdout.write("que[e]: " + str(error_item) + "\n")
			
			#detect and wait for repo-tasks with this release-tag type
			
			for que_item in que_list:
				secondary_obj = koji.ClientSession("%s/kojihub" % (secondary_url))
				build_info = koji_state(que_item["srpm_name"], primary_repo, secondary_obj)
				if (build_info):
					que_item["que_state"] = build_info["state"]
			
			time.sleep(wait_time)
		
		''' ********************************************************
		    * Delete any uneeded files and sleep for the next loop *
		    ******************************************************** '''
		
		#list all of the files in the pwd and delete them
		
		sys.exit(0)
		
		sys.stderr.write("[info] sleeping..." + "\n")
		time.sleep(5 * 60)

if (__name__ == "__main__"):
	main(sys.argv)
