#!/usr/bin/env python2.6

import logging as conflictlogging
import configuration
from couchdbkit import Server, Consumer
from couchdbkit.loaders import FileSystemDocsLoader
import sys
import time
import os

class BaseDatabaseMaintainer(object):
	db_uri = None
	dbname = None
	dbserver = None
	db = None
	logger = None
	def __init__(self, database_uri=None, dbname=None):
		'''
		Create a Server object, initiate connection and set up the databse URI 
		(Not particulary in that order :-)
		Oh and also sync up the views from the on disk storage onto CouchDB
		so we can use them for our maintainance operations.
		'''
		self.logger = configuration.get_logger(logging_instance=conflictlogging,
							system_name='dbmaintainer')
		configuration.info(self.logger)
		self.logger.info('Database maintainer starting.')
		if not database_uri:
			database_uri = "http://127.0.0.1:5984"
		if not dbname:
			dbname = 'session_store'
		self.dbname = dbname
		self.db_uri = database_uri
		self.dbserver = Server(self.db_uri)
		loader = FileSystemDocsLoader('/root/relaxession/_design/')
		try:
			self.db = self.dbserver.get_or_create_db(self.dbname)
			loader.sync(self.db, verbose=True)
		except Exception as e:
			self.logger.info('Init error: %s' % e)
			sys.exit(1)
		self.db.res.put('/_revs_limit',str(configuration.REVS_LIMIT))
	def compact(self):
		raise NotImplemented
	def session_purge(self):
		raise NotImplemented
		
class DatabaseMaintainer(BaseDatabaseMaintainer):
	"""
	A conflict resolver that expects a 'timestamp' field in each document
	chooses the one that's most recent according to the timestamp and makes it
	the prevailing version. It does this only if there is not a time difference between
	the handled doc's timestamp and the conflicting version of more
	than configuration.CONFLICT_LAG_DURATION

	"""
	viewname = None
	lock_file = '/tmp/unusable.relaxession'
	def __init__(self, database_uri=None, dbname=None, viewname='sessiondoc/stale_sessions'):
		BaseDatabaseMaintainer.__init__(self, database_uri, dbname)
		self.viewname = viewname
	def session_purge(self, compact=False):
		self.online(online_flag=False)
		self.logger.info('Querying database.')
		results = self.db.view('sessiondoc/stale_sessions')
		for line in results:
			doc_id = line['key']
			value  = line['value']
			rev = value[0]
			timestamp = value[1]
			self.logger.info('Deleting doc: %s' % doc_id)
			try:
				self.db.delete_doc(doc_id)
			except Exception as e:
				self.logger.info('Error deleting: %s' % e)
		self.online(online_flag=True)
		if compact:
			self.compact()
	def compact(self):
		self.logger.info('Starting compaction.')
		self.db.compact()
		# compact the design document
		self.db.compact('sessiondoc')
	def active_tasks(self):
		return self.dbserver.active_tasks()
	def online(self, online_flag=True):
		if not online_flag:
			f = file(self.lock_file,'w')
			f.close()
		else:
			try:
				os.unlink(self.lock_file)
			except:
				pass
		

if __name__ == "__main__":
	if len(sys.argv) > 1:
		if sys.argv[1] == "status":
			dbm = DatabaseMaintainer()
			print dbm.active_tasks()
			sys.exit(0)
	dbm = DatabaseMaintainer()
	dbm.session_purge(compact=True)
	print dbm.active_tasks()

	
