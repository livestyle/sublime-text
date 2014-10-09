import sys
import os.path
import logging
import json

base_path = os.path.abspath(os.path.dirname(__file__))
for p in ['', 'livestyle', 'tornado.zip', 'backports.zip']:
	p = os.path.join(base_path, p)
	if p not in sys.path:
		sys.path.append(p)

import tornado.ioloop
import tornado.websocket
import livestyle.server as server
from tornado import gen

# setup logger
server.logger.propagate = False
server.logger.setLevel(logging.DEBUG)
if not server.logger.handlers:
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	ch.setFormatter(logging.Formatter('Emmet LiveStyle: %(message)s'))
	server.logger.addHandler(ch)

# start socket server
# server.start()
# tornado.ioloop.IOLoop.instance().start()

def message_handler(message):
	payload = json.loads(message)
	print('Got message %s' % payload['name'])

def start_app():
	print('Start loop')
	tornado.ioloop.IOLoop.instance().add_future(client_connect(), lambda f: start_app())

@gen.coroutine
def client_connect():
	url = 'ws://127.0.0.1:54000/livestyle'
	try:
		ws = yield tornado.websocket.websocket_connect(url)
	except Exception as e:
		print('Create own server')
		server.start()
		ws = yield tornado.websocket.websocket_connect(url)


	while True:
		msg = yield ws.read_message()
		if msg is None:
			print('No connection')
			break
		message_handler(msg)

start_app()
tornado.ioloop.IOLoop.instance().start()