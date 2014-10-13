# Simple event dispatching mini-framework

class EventDispatcher():
	def __init__(self):
		self._callbacks = {}

	def __del__(self):
		self._callbacks = None

	def on(self, name, callback, once=False):
		for event in name.split():
			if event not in self._callbacks:
				self._callbacks[event] = []

			self._callbacks[event].append({
				'callback': callback,
				'once': once
			})

	def off(self, name, callback=None):
		if name in self._callbacks:
			if callback is None:
				self._callbacks[name].clear()
			else:
				self._callbacks[name] = [c for c in self._callbacks[name] if c['callback'] != callback]

	def once(self, name, callback):
		self.on(name, callback, True)

	def emit(self, name, *args, **kwargs):
		if name in self._callbacks:
			for c in self._callbacks[name]:
				c['callback'](*args, **kwargs)

			self._callbacks[name] = [c for c in self._callbacks[name] if not c['once']]