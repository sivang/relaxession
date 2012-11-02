#!/usr/bin/env python2.6

import logging
import subprocess
import configuration
import urllib2
import shlex
import os
import signal


"""
Example invocation for autossh:
autossh -f -N -L9001:localhost:5984 root@example.com
"""


def couchdbTunnel(hosts):
	"""
	This takes a list of target real ip hosts and creates
	a tunnel from localhost:900x up to the number of the
	hosts to each remote_host:5984 port to tunnel couchdb
	connection made by and maintained by for example, something
	like the connman.ConnectionManager class.
	"""
	p = 1
	m = 0
	tunnels = {}
	local_ip = configuration.MY_IP
	for i in hosts:
		if (i != local_ip):
			autoSSH(i, 
				configuration.MONITOR_BASE_PORT + m,
				configuration.BASE_PORT + p, 
				configuration.COUCHDB_PORT, 
				configuration.TUNNEL_USER)
			tunnels[configuration.BASE_PORT + p] = (i,
								configuration.MONITOR_BASE_PORT + m,
								configuration.BASE_PORT + p,
								configuration.COUCHDB_PORT,
								configuration.TUNNEL_USER)
		p += 1
		m += 2
	return tunnels

def populateTunnelTable(hosts):
	p = 1
	m = 0
	tunnels = {}
	local_ip = configuration.MY_IP
	for i in hosts:
		if (i != local_ip):
			tunnels[configuration.BASE_PORT + p] = (i,
								configuration.MONITOR_BASE_PORT + m,
								configuration.BASE_PORT + p,
								configuration.COUCHDB_PORT,
								configuration.TUNNEL_USER)
		p += 1
		m += 2
	return tunnels

def findSSH(target_host, monitor_port, local_port, remote_port, remote_user, logger):
	p = subprocess.Popen(['/bin/ps','-ef'], shell=False, stdout=subprocess.PIPE)
	matching = []
	for l in p.stdout:
		match = ((l.find('ssh') > -1) and
			(l.find(target_host) > -1) and
			# using str(x) here since passing pure number
			# makes .find() barf terribly!
			(l.find(str(local_port)) > -1) and
			(l.find(str(remote_port)) > -1) and
			(l.find(remote_user) > -1))
		if match:
			logger.info('line MATCH: %s' % l)
			matching.append(l)
	# return the pid
	if len(matching) > 0 and matching[0].strip():
		return matching[0].strip().split()[1]
	else:
		return -1
		
	

def autoSSH(target_host, monitor_port, local_port, remote_port, remote_user, logger):
	# monitor_port is not used anymore, residual of formly using autossh we is below
	# quality bar and should not be used.
	command_line = "/usr/bin/ssh -f -N -L%d:127.0.0.1:%d %s@%s"
	to_exec = command_line % (local_port, remote_port, remote_user, target_host)
	logger.info('Preparing to execute: %s' % to_exec)
	logger.info('Checking to see if this SSH tunnel process is running.')
	pid = int(findSSH(target_host, monitor_port, local_port, remote_port, remote_user, logger))
	logger.info("pid: %d" % pid)
	if pid > 0:
		logger.info('SSH tunnel process running. Killing before starting a fresh one.')
		os.kill(pid, signal.SIGTERM)
	else:
		logger.info('SSH not running, starting new: %s' % to_exec) 
	args = shlex.split(to_exec)
	print args
	print "tunnel -> %s" % to_exec
	ret = subprocess.check_call(args, shell=False)

	
