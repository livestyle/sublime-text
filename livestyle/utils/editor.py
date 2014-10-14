"""
Utility method for Sublime Text editor
"""

import re
import sublime
import sublime_plugin
from binascii import crc32

_settings = None
_sels = {}

try:
	isinstance("", basestring)
	def isstr(s):
		return isinstance(s, basestring)
except NameError:
	def isstr(s):
		return isinstance(s, str)

def main_thread(fn):
	"Run function in main thread"
	return lambda *args, **kwargs: sublime.set_timeout(lambda: fn(*args, **kwargs), 1)

def get_setting(name, default=None):
	global _settings
	if not _settings:
		_settings = sublime.load_settings('LiveStyle.sublime-settings')

	return _settings.get(name, default)

def selector_setting(syntax):
	key = '%s_files_selector' % syntax
	if key not in _sels:
		_sels[key] = get_setting(key, 'source.%s' % syntax)

	return _sels[key]

def parse_json(data):
	return json.loads(data) if isstr(data) else data

def content(view):
	"Returns content of given view"
	return view.substr(sublime.Region(0, view.size()))

def file_name(view):
	"Returns file name representation for given view"
	return view.file_name() or temp_file_name(view)

def temp_file_name(view):
	"Returns temporary name for (unsaved) views"
	return '<untitled:%d>' % view.id()

def all_views():
	"Returns all view from all windows"
	views = []
	for w in sublime.windows():
		for v in w.views():
			views.append(v)

	return views

def view_for_buffer_id(buf_id):
	"Returns view for given buffer id"
	for view in all_views():
		if view.buffer_id() == buf_id:
			return view

	return None

def view_for_uri(path):
	"Locates editor view with given URI"
	for view in all_views():
		if file_name(view) == path:
			return view

	return None

def focus_view(view):
	# looks like view.window() is broken in ST2,
	# use another way to find parent window
	for w in sublime.windows():
		for v in w.views():
			if v.id() == view.id():
				return w.focus_view(v)

def view_hash(view):
	return hash(content(view))

def hash(content):
	return crc32(content)

##################################
# Editor locking, used to disable
# diff requests when editor is
# updated after patching
##################################

_locks = set()

def lock(view):
	_locks.add(view.buffer_id())

def unlock(view):
	_locks.discard(view.buffer_id())

def is_locked(view):
	return view.buffer_id() in _locks

#############################

def supported_views(syntaxes):
	"Returns list of opened views matching given syntax list"
	views = []
	for view in all_views():
		v = is_supported_view(view, syntaxes)
		if v:
			views.append(v)

	return views

def supported_files(syntaxes):
	"Returns list of opened files with given syntaxes"
	return [file_name(sv['view']) for sv in supported_views(syntaxes)]

def is_supported_view(view, syntaxes, strict=False):
	"Check if given view matches given syntax"

	for syntax in syntaxes:
		sel = selector_setting(syntax)
		if not view.file_name() and not strict:
			# For new files, check if current scope is text.plain (just created)
			# or it's a strict syntax check
			sel = '%s, text.plain' % sel

		if view.score_selector(0, sel) > 0:
			return {
				'view': view,
				'syntax': syntax
			}

#####################################


def unindent_text(text, pad):
	"""
	Removes padding at the beginning of each text's line
	@type text: str
	@type pad: str
	"""
	lines = text.splitlines()
	
	for i,line in enumerate(lines):
		if line.startswith(pad):
			lines[i] = line[len(pad):]
	
	return '\n'.join(lines)

def get_line_padding(line):
	"""
	Returns padding of current editor's line
	@return str
	"""
	m = re.match(r'^(\s+)', line)
	return m and m.group(0) or ''
