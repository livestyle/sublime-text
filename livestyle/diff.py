"""
When `diff()` method is called, sends `calculate-diff` request to patching
server and wait until either `diff` or `error` response is received.
Until that all other `diff()` requests are queued to lower the pressure
to patcher and save system resources
"""

import logging
import livestyle.client as client
import livestyle.utils.editor as editor_utils
from time import time

_state = {
	'locked_by': None,
	'created': 0,
	'pending': []
}
"Contains data about currently performing diff request"

wait_timeout = 10
"Duration, in seconds, after which performing diff lock considered obsolete"

logger = logging.getLogger('livestyle')

def diff(view):
	uri = editor_utils.file_name(view)
	if uri not in _state['pending']:
		logger.debug('Pending patch request for %s' % uri)
		_state['pending'].append(uri)

	next_queued()

def next_queued(release=False):
	"Move to next queued diff request, if possible"
	
	if release:
		logger.debug('Release diff lock')
		_state['locked_by'] = None

	# make sure current command lock is still valid
	if _state['locked_by'] and _state['created'] < time() - wait_timeout:
		logger.debug('Waiting response is obsolete, reset')
		_state['locked_by'] = None

	if not _state['locked_by'] and _state['pending']:
		uri = _state['pending'].pop(0)
		view = editor_utils.view_for_uri(uri)
		if not view:
			# looks like view for pending diff is already closed, move to next one
			logger.debug('No view, move to next queued diff item')
			return next_queued()


		logger.debug('Send "calculate-diff" message')
		_state['locked_by'] = uri
		_state['created'] = time()
		client.send('calculate-diff', editor_utils.payload(view))
		
	else:
		logger.debug('Diff lock, waiting for response')

@client.on('diff')
def handle_diff_response(data):
	logger.debug('Got diff response for %s' % data['uri'])
	if _state['locked_by'] and _state['locked_by'] == data['uri']:
		logger.debug('Release diff lock, move to next item')
		next_queued(True)

@client.on('error')
def handle_error_response(data):
	if not isinstance(data, dict) or 'origin' not in data:
		# old client? assume it's an error from calculate-diff message
		return next_queued(True)

	origin = data['origin'] or {}
	if origin.get('name') == 'calculate-diff' and _state['locked_by'] and _state['locked_by'] == origin.get('uri'):
		next_queued(True)
