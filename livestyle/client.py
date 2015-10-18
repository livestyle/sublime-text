# A Tornado-based implementation of LiveStyle client
import tornado.websocket
import json
import logging
from tornado import gen
from event_dispatcher import EventDispatcher

dispatcher = EventDispatcher()
logger = logging.getLogger('livestyle')
sock = None

@gen.coroutine
def connect(host='ws://127.0.0.1', port=54000, endpoint='/livestyle'):
	"Connects to LiveStyle server"
	global sock

	if connected():
		logger.debug('Client already connected')
		return

	url = '%s:%d%s' % (host, port, endpoint)
	sock = yield tornado.websocket.websocket_connect(url)

	dispatcher.emit('open')
	logger.debug('Connected to server at %s' % url)

	while True:
		msg = yield sock.read_message()
		if msg is None:
			sock = None
			logger.debug('Disconnected from server')
			dispatcher.emit('close')
			return
		_handle_message(msg)

def connected():
	return sock != None

def send(name, data=None):
	"Sends given message with optional data to all connected LiveStyle clients"
	if sock:
		payload = {
			'name': name,
			'data': data
		}
		logger.debug('Sending message "%s"' % name)
		sock.write_message(json.dumps(payload))
	else:
		logger.info('Unable to send "%s" message: socket is not connected' % name)
	
@gen.coroutine
def send_async(name, data=None):
	"Sends given message with optional data to all connected LiveStyle clients"
	if sock:
		payload = {
			'name': name,
			'data': data
		}
		logger.debug('Sending message "%s"' % name)
		yield sock.write_message(json.dumps(payload))
	else:
		logger.info('Unable to send "%s" message: socket is not connected' % name)
		yield False

def _handle_message(message):
	payload = json.loads(message)
	logger.debug('Received message "%s"' % payload['name'])
	dispatcher.emit(payload['name'], payload.get('data'))

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