"""
When `diff()` method is called, sends `calculate-diff` request to patching
server and wait until either `diff` or `error` response is received.
Until that all other `diff()` requests are queued to lower the pressure
to patcher and save system resources
"""

import logging
import livestyle.client as client
import livestyle.utils.editor as editor_utils
import sublime
from tornado.ioloop import IOLoop
from threading import Thread
from time import time

waiting_response = [None]
"Contains data about currently performing diff request"

wait_timeout = 10
"Duration, in seconds, after which performing diff considered obsolete"

pending = [] # must be ordered list(), not set()
"List pending diff documents"

logger = logging.getLogger('livestyle')

def diff(view):
	uri = editor_utils.file_name(view)
	if uri not in pending:
		logger.info('Pending patch request for %s' % uri)
		pending.append(uri)

	next_queued()

def next_queued(release=False):
	"Move to next queued diff request, if possible"
	
	if release:
		logger.info('Release diff lock')
		waiting_response[0] = None

	# make sure current command lock is still valid
	if waiting_response[0] and waiting_response[0]['created'] < time() - wait_timeout:
		logger.info('Waiting response is obsolete, reset')
		waiting_response[0] = None

	if not waiting_response[0] and pending:
		uri = pending.pop(0)
		view = editor_utils.view_for_uri(uri)
		if not view:
			# looks like view for pending diff is already closed, move to next one
			logger.info('No view, move to next queued diff item')
			return next_queued()


		logger.info('Send "calculate-diff" message')
		waiting_response[0] = {'uri': uri, 'created': time()}
		start = time()

		payload = editor_utils.payload(view)
		logger.info('Created payload in %f' % (time() - start))

		# client.send_async('calculate-diff', editor_utils.payload(view))
		def _done(f):
			logger.info('Message sent in %f' % (time() - start))

		def _send(): 
			IOLoop.current().add_future(client.send_async('calculate-diff', payload), _done)
		# _send_message = lambda: client.send_async('calculate-diff', editor_utils.payload(view))

		# sublime.set_timeout_async(_send, 1)
		thread = Thread(target=_send)
		thread.daemon = True
		thread.start()
	else:
		logger.info('Diff lock, waiting for response')

def send_message(payload):
	logger.info('__send message')
	client.send_async('calculate-diff', payload)


@client.on('diff')
def handle_diff_response(data):
	logger.info('Got diff response for %s' % data['uri'])
	if waiting_response[0] and waiting_response[0]['uri'] == data['uri']:
		logger.info('Release diff lock, move to next item')
		next_queued(True)

@client.on('error')
def handle_error_response(data):
	if not isinstance(data, dict) or 'origin' not in data:
		# old client? assume it's an error from calculate-diff message
		return next_queued(True)

	origin = data['origin'] or {}
	if origin.get('name') == 'calculate-diff' and waiting_response[0] and waiting_response[0]['uri'] == origin.get('uri'):
		next_queued(True)
