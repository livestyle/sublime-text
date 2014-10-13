# A Tornado-based implementation of LiveStyle client
import tornado.websocket
import json
from tornado import gen
from event_dispatcher import EventDispatcher

dispatcher = EventDispatcher()
sock = None

@gen.coroutine
def connect(host='ws://127.0.0.1', port=54000, endpoint='/livestyle'):
	"Connects to LiveStyle server"
	global sock
	url = '%s:%d%s' % (host, port, endpoint)
	sock = yield tornado.websocket.websocket_connect(url)

	dispatcher.emit('open')

	while True:
		msg = yield sock.read_message()
		if msg is None:
			dispatcher.emit('close')
			return
		_handle_message(msg)

def send(name, data=None):
	"Sends given message with optional data to all connected LiveStyle clients"
	if sock:
		payload = {
			'name': name,
			'data': data
		}
		sock.write_message(json.dumps(payload))

def _handle_message(message):
	payload = json.loads(message)
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