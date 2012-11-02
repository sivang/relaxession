#!/usr/bin/env python2.6

COPYRIGHT="""
Copyright (C) 2010 Sivan Greenberg
"""

MIT_LIC="""
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


"""
This holds misc configuration stuff for Relaxession

 7 To set this iteration of relaxession on an array of servers
 8 do the following:
 9 
10         1) Modify NODE_LIST to list IPs of all servers that
11            participate in the replication scheme.
12         2) Set the port where CouchDB server is running on the
13            target host(s). Local CouchDB is assumed to run on
14            its default 5894 port.
15         3) Set the MONITOR_BASE_PORT to a value you know is not
16            used for other services on the target and local systems.
17            Note that per each target node autossh will use 2 ports
18            for the heartbeat loop. 
19            So for instance, if you have 2 servers and you leave
20            the default port number, you have to make sure ports
21            50000 to 50003 are not.
22         4) Set the BASE_PORT to a desired value. This is what
23            relaxession uses to establish the local listening sockets
24            for the SSH tunnels to the counter part nodes.
25            So, like mentioned before, the port range from the BASE_PORT
26            to the number of taget nodes you have need to be free
27            of any other service.
28         5) Set TUNNEL_USER to a sensible value; This is the user that
29            will be passed to autossh/ssh to be able to establish the
30            tunnels. 
31            Note that SSH pub/priv keys should be used or otherwise
32            passwords for the user at the respective hosts will have
33            to be inserted manually which will block recurrent connection
34            established after a service drop.
	   6) Set MONITOR_INTERVAL to control how often replication connections
	      are checked and re-brought live after a service drop.

"""

import logging
from optparse import OptionParser
import urllib2
import os
from couchdbkit import Server

PRODUCTION = False
SYSTEM_NAME = 'configuration'
NODE_HELLO = "{'couchdb': 'Welcome', 'version': '0.11.0'}"

if PRODUCTION:
	NODE_LIST = [ '85.17.233.129', '173.45.121.18', '216.75.11.76', '82.103.128.198' ]
else:
	NODE_LIST = [ '10.200.10.157', '10.200.10.138', '10.200.10.152' ]

NODE_LIST = [ '192.168.1.100', '192.168.1.103' ]

COUCHDB_PORT = 5984
BASE_PORT = 9000
MONITOR_BASE_PORT = 50000
TUNNEL_USER = 'root'
MONITOR_INTERVAL = 5
LOG_PATH = "/root/relaxession"
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = '%(asctime)s %(message)s'
CONFLICT_LAG_DURATION = 1 # changing it to 1 minute after time experiments we did on the servers
REVS_LIMIT = 200

def log_filename(prefix=__name__):
	return "".join([LOG_PATH, '/', prefix, '.log'])




def excludeMyIP(hosts, extract=False):
	for i in hosts:
		if extract:
			a_target_ip = i.split(':')[1].strip('//')
		else:
			a_target_ip = i
		if a_target_ip == MY_IP:
			hosts.remove(i)

def get_ip_address():
	return os.popen('perl /root/find_local_ip.pl').readline().strip()


def get_logger(logging_instance,
				system_name='configuration', 
				logging_level=logging.INFO,	
				logging_format='%(asctime)s %(message)s'):
	filename = log_filename(system_name)
	logging_instance.basicConfig(filename=filename,
				level=logging_level,
				format=logging_format)
	return logging_instance.getLogger(system_name)

MY_IP = get_ip_address()
excludeMyIP(NODE_LIST)
print NODE_LIST

def info(logger):
	s = Server()
	node_hello = s.info()
	logger.info('== Configuration ==')
	logger.info('CouchDB: %s ===' % node_hello)
	logger.info('Target hosts: %s' % NODE_LIST)
	logger.info('This host''s IP: %s', MY_IP)
	logger.info('CouchDB expected at port %s' % COUCHDB_PORT)
	logger.info('Tunnel user for SSH: %s' % TUNNEL_USER)
	logger.info('Monitoring interval for connections: %s seconds.' % MONITOR_INTERVAL)
	logger.info('Log path: %s' % LOG_PATH)



if __name__ == "__main__":
	'''
	Have a main entry point so configuration.py could be used to upload
	Relaxession configuration to CouchDB , and CouchDB will be used
	for the configuration storage and propogation to all nodes.
	'''
	s = Server()
	node_hello = s.info()
	logger = get_logger(logging_instance=logging,
				system_name=SYSTEM_NAME,
				logging_level=LOGGING_LEVEL,
				logging_format=LOGGING_FORMAT)
	info(logger)
	parser = OptionParser()
	parser.add_option("--sync", help="Sync the configuration data from configuration.py to CouchDB. "
					 "This starts a propogation process to all nodes in the NODE_LIST "
					 "And the configuration changes handler will pull them and apply "
					 "at each node's end. This will have to either trigger a restart "
					 "of the ConnectionManager or refresh the config vars in memory "
					 "and continue then. Remains to taken care by the implementation.")
	parser.add_option("--local-sync", help="Like --sync, but sync up against the local CouchDB only. "
						"Useful when you want to experiment with config values without "
						"affecting the remote nodes.")
	(options, args) = parser.parse_args()
	# This could probably be done the following way:
	#	- Read the config data from the respective CouchDB config db and documents.
	#	- Set it the attribute way into the configuration module:
	#		configuration.NODE_LIST = ....
	#		configuration.COUCHDB_PORT = ..
	#		configuration.BASE_PORT = ..
	#		configuration.MONITOR_BASE_PORT = ..
	#		configuration.TUNNEL_USER = ...
	#	- Then stop the manageForever() from ConnectionManager, which should be run
	#	  in a seperate thread / process to be able to close it.
	#	- Instantiate the new class with the new config params.
	#	- Refork or re-thread it for the manageForever() method.

			



