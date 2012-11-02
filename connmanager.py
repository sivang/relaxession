#!/usr/bin/env python

import logging as connlogging
from multiprocessing import Process
import configuration
from couchdbkit import Server
from multiprocessing import Queue
import time
import urllib2
import autotunnel
import sys


class Probe(Process):
	online = False
	response_time = 0
	logger = None
	def __init__(self, targets_queue, online_list, offline_list):
		self.targets_queue = targets_queue  # get a reference to the targets holding queue.
		self.online_list  = online_list # get a reference to the online_list for populating it
		self.offline_list = offline_list # ditto 
		self.logger = configuration.get_logger(logging_instance=connlogging,
							system_name='connmanager')
		Thread.__init__(self)
	def run(self):
		self.target = self.targets_queue.get()
		self.dbserver = Server(self.target)
		try:
			self.logger.info('Trying: %s' % self.target)
			start_time = time.time()
			info = self.dbserver.info() # this is actually the proper request
			end_time = time.time()
		except Exception as e:
			print "CRITICAL: failed connect to %s , %s. Offline!" % (self.target, e)
			self.logger.info(
				'Failed to connect to [%s]. Out of the online queue!' % self.target)
			print "Restaring SSH"
			self.logger.info('Restarting SSH tunnel for %s' % self.target)
			self.online = False
			self.offline_list.append(self.target)
		else:
			self.logger.info('%s seems online.' % self.target)
			self.online = True
			self.response_time = end_time - start_time
			# maintain a list of online nodes, with the response_time as the key
			# for easy sorting afterwards so we can always re-start replication connections
			# from fastest reponding node to the rest.
			self.online_list.append((self.response_time, self.target))
		finally:
			self.logger.info('Probe finsihed.')
			self.targets_queue.task_done()

class NodeProbe(object):
	"""
	The NodeProbe takes a list of hosts and surveys them for responsiveness.
	The result is stored in the 'available' list argument holding IPs of hosts from 
	the most responsive to the least.
	Nodes that did not respond in the timeout defined are put in the 'offline' 
	list argument.
	"""
	timeout = 0 
	hosts = None
	logger = None
	queue = Queue() # queue holding to list of hosts to survey that we populate from the constructor
	def __init__(self,hosts, available, offline):
		self.logger = configuration.get_logger(logging_instance=connlogging,
							system_name='connmanager')
		self.hosts = hosts
		self.available = available
		self.offline = offline
		for i in self.hosts:
			self.queue.put(i)
	def survey(self):
		for h in self.hosts:
			# create threads the same number as number of hosts to scan for maximum
			# parallel operation.
			self.logger.info("Starting survey for %s." % h)
			Probe(self.queue, self.available, self.offline).start()
	def wait_finish(self):
		self.logger.info("Waiting for probing threads to finish.")
		self.queue.join()


class ConnectionManager(object):
	"""
	This class takes care of starting the wrapper SSH tunnel connections to allow
	communicating with the remote CouchDB nodes, and is responsible for restarting
	replication connections for nodes that go back into online state as reported
	by the NodeProbe.
	"""
	def __init__(self, hosts, database_name="session_store"):
		self.logger = configuration.get_logger(logging_instance=connlogging,
								system_name='connmanager')
		configuration.info(self.logger)
		self.database_name = database_name
		self.hosts = hosts
		self.online  = []
		self.ip = self.get_ip_address()
		self.logger.info('= ConnectionManager instantiated =')
		self.logger.info("My IP -> %s" % self.ip)
		self.logger.info("Targets: %s" % self.hosts)
		# Create an instance to the local server
		self.dbserver = Server()
		self.node_probe = None # reference for the NodeProbe object
	def manage(self):
		'''This encapsulates one monitoring run'''	
		# clear latest run results 
		# (if not our lists get inifnitely populated)
		self.online = []
		self.offline = []
		# start the monitor run
		self.logger.info('Monitor run for %s' % self.hosts)
		self.node_probe = NodeProbe(self.hosts, self.online, self.offline)
		self.node_probe.survey()
		self.node_probe.wait_finish()
		print "online: %s" % self.online
		print "offline: %s" % self.offline
		for i in self.online:
			self.logger.info('%s online. Restarting connection.' % i[1])
			self.restartConnection(i[1])

	def get_ip_address(self):
		return configuration.MY_IP

	def restartConnection(self, target_uri):
		"""
		This wrapper may look redundant, but it is here to
		remind us that eventually SSH tunneling will be handled by
		'self.startTunnel' and will be called before 'self.continuousReplication'.

		This will mandate the translation of the real ip addresses to localhost
		and respective port to make the SSH tunneling transparent to users of 
		the ConnectionManager. So once it is finished, target nodes list will be fetched
		from the configuration CouchDB db and translated to tunnel invocations 
		and localhost replication connections.
		"""
		self.logger.info('Restarting conn. for  %s' % target_uri)
		self.continuousReplication(target_uri, self.database_name)

	def manageForever(self, interval=30):
		while True:
			self.manage()
			time.sleep(interval)

	def startTunnel(self, local_port, local_host, target_port, target_host):
		"""
		If not already started, start a new autoSSH process to 
		keep the connection to the target.
		If the autossh process is already there, leave it since autossh
		takes care of maintaining the connection.

		Return the 'http://localhost:900x' equivalent for the real ip and port.
		e.g: 'http://79.143.23.119:5984' --> 'http://localhost:9001'
		This enables transparent restart of the CouchDB plain text HTTP replication
		connections.
		"""
	def continuousReplication(self, target_uri, database_name):
		"""
		Stop continuous replication to target_uri if exists.
		then, start it fresh.
		< rnewson> sivang: you can cancel a replication with "cancel":true but 
		they are not automatically restarted if they crash. However:
		According to rnewson starting connection reuses a previous connection if it existed,
		we don't really need to do anything.
		Just - Start the continuous replication again for every node that came back online,
		and forget about it! yes, it is THAT easy.
		This is after all, CouchDB. Time to relax.
		"""
		target_uri_db = "%s/%s" % (target_uri, database_name)
		self.logger.info('Start Cont. rpct. : %s' % target_uri_db)
		# direction of replication is changed to pull replication instead
		# of push, as recommended by the CouchDB wiki for better performance.
		self.dbserver.replicate(source=self.database_name,
					target=target_uri_db,
					continuous=True)


def sessionReplicationManage():
		# start the ssh tunnels with autossh
		tunnels = autotunnel.couchdbTunnel(configuration.NODE_LIST)
		print 'tunnels = %s' % tunnels
		myhosts = []
		port = configuration.BASE_PORT
		for node in configuration.NODE_LIST:
			port += 1
			myhosts.append('http://localhost:%d' % port)
		conman = ConnectionManager(myhosts)
		conman.manageForever(interval=configuration.MONITOR_INTERVAL)



if __name__ == "__main__":
	"""
	Test monitor from localhost (this host) to a list of target couchdb
	test host nodes. Take care for starting the SSH tunnels with keepalive
	provided by autossh.

	Take care for port specifying including the monitor port juggling for autossh.
	"""
	sessionReplicationManage()
	
