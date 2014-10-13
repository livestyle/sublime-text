import sys
import os.path
import logging
import json

base_path = os.path.abspath(os.path.dirname(__file__))
for p in ['', 'livestyle', 'tornado.zip', 'backports.zip']:
	p = os.path.join(base_path, p)
	if p not in sys.path:
		sys.path.append(p)

import livestyle.server as server
import livestyle.client as client
from tornado import gen
from tornado.ioloop import IOLoop

# setup logger
server.logger.propagate = False
server.logger.setLevel(logging.DEBUG)
if not server.logger.handlers:
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	ch.setFormatter(logging.Formatter('Emmet LiveStyle: %(message)s'))
	server.logger.addHandler(ch)

def start_app():
	print('Start app')
	IOLoop.instance().add_future(client_connect(), restart_app)

def restart_app(f):
	print('Restarting app because %s' % f.exception())
	IOLoop.instance().call_later(1, start_app)

@client.on('editor-connect')
def on_editor_connect(data):
	print('Editor connected')

@client.on('open')
def on_open(*args):
	print('Connected to server')

@client.on('open client-connect')
def identify(*args):
	print('Identify')
	client.send('editor-connect', {'id': 'st3', 'title': 'Sublime Text 3'})

@gen.coroutine
def client_connect():
	try:
		yield client.connect()
	except Exception as e:
		print('Create own server because %s' % e)
		server.start()
		yield client.connect()
	
start_app()
tornado.ioloop.IOLoop.instance().start()