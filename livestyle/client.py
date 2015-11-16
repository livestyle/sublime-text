# A Tornado-based implementation of LiveStyle client
# In Tornado, a WebSocket client implementation writes data
# into socket in blocking manner. Generally, this is not an issue
# because most messages a very small. But if you try to edit a very large CSS,
# the UI (main) thread becomes unresponsive for a while. In my test,
# editing a 500KB CSS file causes 350ms delay.
# To solve this issue, socket writing is performed in separate thread
# and all messages are putted into queue first
import tornado.websocket
import json
import logging
import sublime
from threading import Thread
from tornado import gen
from tornado.ioloop import IOLoop
from event_dispatcher import EventDispatcher

dispatcher = EventDispatcher()
logger = logging.getLogger('livestyle')
sock = None
_state = {
	'locked': False, 
	'queue': []
}

def main_thread(fn):
	"Run function in main thread"
	return lambda *args, **kwargs: sublime.set_timeout(lambda: fn(*args, **kwargs), 1)

@gen.coroutine
def connect(host='ws://127.0.0.1', port=54000, endpoint='/livestyle'):
	"Connects to LiveStyle server"
	global sock

	if connected():
		logger.debug('Client already connected')
		return

	url = '%s:%d%s' % (host, port, endpoint)
	sock = yield tornado.websocket.websocket_connect(url)

	_emit('open')
	_reset_queue()
	logger.debug('Connected to server at %s' % url)

	while True:
		msg = yield sock.read_message()
		if msg is None:
			sock = None
			logger.debug('Disconnected from server')
			_reset_queue()
			_emit('close')
			return
		_handle_message(msg)

def connected():
	return sock != None

def send(name, data=None):
	"Enqueues given message with optional data to all connected LiveStyle clients"
	logger.debug('Enqueue message "%s"' % name)
	_state['queue'].append((name, data))
	_next_in_queue()

def _handle_message(message):
	payload = json.loads(message)
	logger.debug('Received message "%s"' % payload['name'])
	_emit(payload['name'], payload.get('data'))

def on(name, callback=None):
	if callback is None: # using as decorator
		return lambda f: dispatcher.on(name, f)
	dispatcher.on(name, callback)

def off(name, callback=None):
	dispatcher.off(name, callback)

def once(name, callback=None):
	if callback is None: # using as decorator
		return lambda f: dispatcher.once(name, f)
	dispatcher.once(name, callback)

@main_thread
def _emit(name, payload=None):
	dispatcher.emit(name, payload)

# Message queuing

def _next_in_queue():
	if _state['locked']:
		logger.debug('Queue is locked')
		return

	if not _state['queue']:
		logger.debug('Queue is empty, nothing to send')
		return

	if not sock:
		logger.debug('Unable to send message: socket is not connected')
		return

	_state['locked'] = True
	msg = _state['queue'].pop(0)
	payload = {
		'name': msg[0],
		'data': msg[1]
	}

	def _send(): 
		logger.debug('Sending message "%s"' % payload['name'])
		IOLoop.current().add_future(sock.write_message(json.dumps(payload)), _on_message_sent)

	Thread(target=_send).start()

def _on_message_sent(f=None):
	_state['locked'] = False
	_next_in_queue()

def _reset_queue():
	_state['locked'] = False
	_state['queue'][:] = [] # instead of .clear(), unsupported in 2.6