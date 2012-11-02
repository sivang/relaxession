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



import logging as conflictlogging
import configuration
from couchdbkit import Server, Consumer
from couchdbkit.loaders import FileSystemDocsLoader
from multiprocessing import Process
import sys
import time
import datetime


## checkpoint:
## changing the resolution approach to delete all the conflicting docs and save the
## winning one using a bulk_save call, to try and silence the changes feed
## when reporting the doc that was in conflict, while deleting its conflicts
## which makes our handler confused.

## checkpoint #2
## using async processes to enable
## multi processing of conflicts

def timeDelta(bigger_ts, smaller_ts, minutes):
	minutes_delta = datetime.timedelta(minutes=minutes)
	return (datetime.datetime.fromtimestamp(float(smaller_ts)) < 
			(datetime.datetime.fromtimestamp(float(bigger_ts)) - minutes_delta ))

class BaseConflictResolver(object):
	"""
	Base class for all the conflict resolver classes that can be treated like plugin.
	"""
	db_uri = None
	dbname = None
	dbserver = None
	conflicts = None
	db = None
	conflict = None
	logger = None
	def __init__(self, database_uri=None, dbname=None):
		'''
		Create a Server object, initiate connection and set up the databse URI 
		(Not particulary in that order :-)
		Oh and also sync up the views from the on disk storage onto CouchDB
		'''
		self.logger = configuration.get_logger(logging_instance=conflictlogging,
							system_name='conflictmanager')
		configuration.info(self.logger)
		self.logger.info('Conflict manager starting.')
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
	def resolve(self):
		raise NotImplemented
	def resolveForever(self):
		raise NotImplemented
		
class LatestTimestampConflictResolver(BaseConflictResolver):
	"""
	A conflict resolver that expects a 'timestamp' field in each document
	chooses the one that's most recent according to the timestamp and makes it
	the prevailing version. It does this only if there is not a time difference between
	the handled doc's timestamp and the conflicting version of more
	than configuration.CONFLICT_LAG_DURATION

	"""
	viewname = None
	def __init__(self, database_uri=None, dbname=None, viewname='sessiondoc/conflicts'):
		BaseConflictResolver.__init__(self, database_uri, dbname)
		self.viewname = viewname
	def _resolve(self, line):
		tag_doc = None
		self.logger.info('feed:')
		self.logger.info(line)
		self.logger.info('-end feed-')
		conf_docid = None
		conf_doc   = None
		winning_doc= None
		# clean timestamped_revs between callbacks
		self.timestamped_revs = []
		self.rev_counted_revs = []
		# self.logger.info(line)
		try:
			conf_docid = line['id']
		except Exception as e:
			self.logger.info("ERROR: No id key in changes line dictionary!")
			self.logger.info('Skipping change.')
			self.logger.info("%s" % e)
			return
		tagid = 'INP__' + conf_docid
		tag_doc = { '_id': tagid, 'INP' : True }
		if (tagid in self.db):
			pass
		else:
			self.db.save_doc(tag_doc)
		try:
			conf_doc = self.db.get(docid=conf_docid, conflicts=True)
		except Exception as e:
			self.logger.info('Error getting document with conflicts:')
			self.logger.info('%s' % e)
			return
		self.logger.info('Handling conflicts for document: %s' % conf_doc)
		self.conflicts = conf_doc.has_key('_conflicts') and conf_doc['_conflicts'] or []
		if not len(self.conflicts):
			self.logger.info('Document lacks _conflicts. Skip')
			sys.exit(-2)
		for conf_rev in self.conflicts:
			doctime = None
			resolve_failed = False
			docid = conf_docid
			conflict_revlist = self.conflicts # we need the list of revs to compare with
			doc = conf_doc
			doctime = doc.has_key('timestamp') and doc['timestamp'] or None
			for r in conflict_revlist:
				conflicting_doc = self.db.get(docid=docid, rev=r)
				if conflicting_doc.has_key('timestamp'):
					self.timestamped_revs.append((int(conflicting_doc['timestamp']),
											conflicting_doc))
				if conflicting_doc.has_key('rev_count'):
					self.rev_counted_revs.append((int(conflicting_doc['rev_count']),
											conflicting_doc))
			self.logger.info('Timestamped Revisions:')
			for i in self.timestamped_revs:
				self.logger.info(i)
			self.logger.info('Revision Counted Revisions:')
			for i in self.rev_counted_revs:
				self.logger.info(i)
			if (len(self.timestamped_revs) == 0) and (len(self.rev_counted_revs)==0):
				self.logger.info('Empty rev_counts/timestamps: Skip.')
				return
			latest_timestamp_rev = max(self.timestamped_revs)
			biggest_rev_count_rev = max(self.rev_counted_revs)
			if (len(latest_timestamp_rev) < 2) and (len(biggest_rev_count_rev) <2):
				self.logger.info('Conflicted without decision field: %s' % latest_timestamp_rev)
				self.logger.info('Skip.')
				return
			# clear the _conflicts field from the
			# doc reported in conflict by
			# the changes feed.
			doc.has_key('_conflicts') and doc.pop('_conflicts')
			# create a list to sort in
			tmp_list = []
			tmp_list.append(latest_timestamp_rev)
			tmp_list.append((int(doctime), doc))
			tmp_list.sort()
			lag = timeDelta(tmp_list[1][0], tmp_list[0][0], configuration.CONFLICT_LAG_DURATION)
			# create a list to sort according
			# to rev count number
			tmp_list2 = []
			tmp_list2.append(biggest_rev_count_rev)
			tmp_list2.append((int(doc['rev_count']), doc))
			tmp_list2.sort()
			if lag:
				self.logger.info('!SESSION LAG! latest timestamp wins.')
				# take latest timestamp, the latest doc is at the tail
				# of this list.
				winning_doc = tmp_list[1][1]
			else:
				self.logger.info('No session lag: longest rev count wins.')
				# winning doc will be the one with the bigger revision
				# count number
				winning_doc = tmp_list2[1][1]
			# remove winning_doc from conflict_revlist, so we won't
			# delete it.
			if winning_doc and winning_doc['_rev'] in conflict_revlist:
				conflict_revlist.remove(winning_doc['_rev'])
			# do the resolving in a bulk update
			bulk_update_list = []
			for r in conflict_revlist:
				doc_for_delete = {}
				doc_for_delete['_id'] = docid
				doc_for_delete['_rev'] = r
				doc_for_delete['_deleted'] = True
				bulk_update_list.append(doc_for_delete)
			if winning_doc: 
				bulk_update_list.append(winning_doc)
			# try to save the decision
			if len(bulk_update_list)!=0:
				self.logger.info('Decision:')
				self.logger.info(bulk_update_list)
				self.db.bulk_save(bulk_update_list)
			else:
				self.logger.info('Empty decision: Skip.')
			# should be deleted at the end, releasing the lock
			if tagid in self.db:
				self.db.delete_doc(tagid)

	def resolveForever(self):
		consumer = Consumer(self.db)
		consumer.register_callback(self.resolve)
		while True:
			try:
				consumer.wait(heartbeat=True, filter="sessiondoc/scanconflicts")
				self.logger.info('Changes feed closed connection. Restarting.')
			except Exception as e:
				self.logger.info('Error connecting to CouchDB for changes:')
				self.logger.info('%s' % e)
				time.sleep(1)
	def resolve(self, line):
		self.logger.info('Spawning resolver process.')
		p = Process(target=self._resolve, args=(line,))
		p.start()
		self.logger.info('PID: %s' % p.pid)
		
		
		
		

if __name__ == "__main__":
	myresolver = LatestTimestampConflictResolver()
	myresolver.resolveForever()
	
