##################################
# File reader utils: returns 
# contents of given file but caches 
# it for later re-use
##################################

import time
import codecs
import os.path
from binascii import crc32

_file_cache = {}

class FileCacheEntity(object):
	read_timeout = 20 # Cache re-read timeout, in seconds
	
	def __init__(self, uri):
		self.uri = uri
		self.last_read = 0
		self.last_access = 0
		self._content = None

	def content(self):
		if self._content and not self.is_valid():
			# content is already loaded, check if it's still valid
			self._content = None

		if self._content is None:
			self.last_read = time.time()
			c = read_file(self.uri)
			if c is None:
				# file doesn't exists anymore
				return None

			self._content = {
				'uri': self.uri,
				'content': c,
				'hash': crc32(bytes(c, 'UTF-8'))
			}

		self.last_access = time.time()
		return self._content

	def is_valid(self):
		"""
		Check if current entry was recently created/updated 
		so there's no need to touch file system to verify
		file state
		"""
		return self.last_read < time.time() + FileCacheEntity.read_timeout

def get_file_contents(uri):
	"Returns given file data: its content and hash"
	uri = uri['uri']
	# first, check if file in cache
	if uri not in _file_cache:
		if os.path.exists(uri):
			_file_cache[uri] = FileCacheEntity(uri)
		else:
			return None

	result = _file_cache[uri].content()
	if result is None:
		del _file_cache[uri]

	return result

def read_file(file_path):
	"Reads file at given path"
	try:
		with codecs.open(file_path, 'r', 'utf-8') as f:
			return f.read()
	except Exception as e:
		return None

