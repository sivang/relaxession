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


import unittest
import time
import datetime

from couchdbkit import Server
from couchdbkit.schema.properties import *

class ConflictResolverTestCase(unittest.TestCase):
	""" Test conflict resolution policy when we're in the state of lag,
	    that is, there's more than 10 minutes time difference between conflicting
	    version of a document: The document with longest rev count wins.
	    If not in a lag, the latest document should win.
	"""
	database_name = 'session_store'
	repdb_name    = 'session_store_rep'
	s  = None
	db = None
	repdb = None
	docid = 'testing_doc'
	doc = None
	replicated_doc = None
	source_rev_count = 0

	def setUp(self):
		"""
		Creating connection to the database according to
		configuration, and creating docs that act in test.
		"""
		self.s = Server('http://localhost:5984')
		assert len(self.s.info())!=0, 'CouchDB server is down or not working properly.'
		self.db = self.s.get_or_create_db(self.database_name)
		self.repdb = self.s.get_or_create_db(self.repdb_name)
		self.doc = {'_id': self.docid,
				'timestamp': str(int(round(time.time()))),
				'text'	   : 'initial text',
				'rev_count': str(self.source_rev_count)}
		# clear previous test residual
		if self.docid in self.db: 
			self.db.delete_doc(self.docid)
		if self.docid in self.repdb:
			self.repdb.delete_doc(self.docid)
		self.db.save_doc(self.doc)
	def tearDown(self):
		pass
		

class RevCountResolutionTestCase(ConflictResolverTestCase):
	"""
	This tests resolution that is based on rev_count, given
	the time difference between two conflicting versions
	is less than configuration.SESSION_LAG_TIME, we can't
	rely on timestamps due to server time skew. 
	So we decide the winning document based on the number 
	of modifications, assuming the one with the largest 
	number of modifs should be the current one.
	"""
	def _runTest(self):
		self.s.replicate(self.database_name, 'http://localhost:5984/'+self.repdb_name)
		self.s = Server('http://localhost:5984')
		self.repdb = self.s.get_or_create_db(self.repdb_name)
		self.replicated_doc = self.repdb.get(self.docid)
		# increasing the revision log (add 6 more revisions)
		for i in range(6):
		        self.replicated_doc['text'] = 'bigger revision number'
			self.replicated_doc['timestamp'] = str(int(round(time.time())))
			self.replicated_doc['rev_count'] = str(int(self.replicated_doc['rev_count']) + 1)
			self.repdb.save_doc(self.replicated_doc)
		# create the conflict, change the same
		# text field of the original at the source database.
		master_db = self.s.get_or_create_db(self.database_name)
		doc = master_db.get(self.docid)
		doc['text'] = 'smaller revision number'
		doc['timestamp'] = str(int(round(time.time())))
		doc['rev_count'] = str(int(doc['rev_count']) + 1)
		master_db.save_doc(doc)
		self.s.replicate('http://localhost:5984/'+self.repdb_name, self.database_name)
		doc = self.db.get(self.docid)
		self.assertEqual(doc['text'], 'bigger revision number')
		start_time = time.time()
		while (self.db.get(self.docid, conflicts=True).has_key('_conflicts')):
			pass
		end_time   = time.time()
		print "Time to conflicts clear: %s" % (end_time - start_time)
			
	def runTest(self):
		for i in range(10):
			self._runTest()

class TimestampResolutionTestCase(ConflictResolverTestCase):
	"""
	If session documents timestamp are more than configuration.SESSION_LAG_TIME
	apart, we treat this situation as if we were out of sync for a while, and hence
	we need to be passive and make the winning version of doc the doc with the latest
	timestamp, which in this situation makes sure we win the docs that came from
	replication.
	"""
	def _runTest(self):
		self.s.replicate(self.database_name, 'http://localhost:5984/'+self.repdb_name)
		local_doc  = self.db.get(self.docid)
		local_doc['timestamp'] = str(int(time.time()) + 120)
		local_doc['text'] = 'this should remain the winning doc, latest timestamp'
		self.db.save_doc(local_doc)
		remote_doc = self.repdb.get(self.docid)
		remote_doc['text'] = 'this should be deleted eventually, as it has older timestamp'
		remote_doc['timestamp'] = str(int(time.time()) - 120)
		self.repdb.save_doc(remote_doc)
		self.s.replicate('http://localhost:5984/'+self.repdb_name, self.database_name)
		start_time = time.time()
		while ('INP__' + self.docid) in self.db:
			print 'waiting..'
		end_time = time.time()
		print "Time until right document saved: %s" % (end_time - start_time)
		local_doc = self.db.get(self.docid)
		self.assertEqual(local_doc['text'], 'this should remain the winning doc, latest timestamp')
		start_time = time.time()
		while (self.db.get(self.docid, conflicts=True).has_key('_conflicts')):
			pass
		end_time = time.time()
		print "Time to conflicts clear: %s" % (end_time - start_time)
	def runTest(self):
		for i in range(10):
			self._runTest()




if __name__ == "__main__":
	unittest.main()
