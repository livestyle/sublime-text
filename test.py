import sys
import os.path
import logging

base_path = os.path.abspath(os.path.dirname(__file__))
for p in ['', 'livestyle', 'tornado.zip', 'backports.zip']:
	p = os.path.join(base_path, p)
	if p not in sys.path:
		sys.path.append(p)

import tornado.ioloop
import livestyle.server as server

# setup logger
server.logger.propagate = False
server.logger.setLevel(logging.DEBUG)
if not server.logger.handlers:
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	ch.setFormatter(logging.Formatter('Emmet LiveStyle: %(message)s'))
	server.logger.addHandler(ch)

# start socket server
server.start()
tornado.ioloop.IOLoop.instance().start()
