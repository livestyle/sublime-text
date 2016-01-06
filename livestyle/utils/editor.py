"""
Utility method for Sublime Text editor
"""

import re
import os.path
import sublime
import sublime_plugin
from zlib import adler32 # adler32 considered faster than crc32

# List of LiveStyle-supported file extensions
supported_syntaxes = ['css', 'less', 'scss']

_settings = None
_sels = {}

try:
	isinstance("", basestring)
	def isstr(s):
		return isinstance(s, basestring)

	def hash(content):
		return adler32(content)
except NameError:
	def isstr(s):
		return isinstance(s, str)

	def hash(content):
		return adler32(bytes(content, 'UTF-8'))

def main_thread(fn):
	"Run function in main thread"
	return lambda *args, **kwargs: sublime.set_timeout(lambda: fn(*args, **kwargs), 1)

def get_setting(name, default=None):
	settings = sublime.load_settings('LiveStyle.sublime-settings')
	return settings.get(name, default)

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
	return '[untitled:%d]' % view.id()

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

def supported_views():
	"Returns list of opened views matching given syntax list"
	views = []
	for view in all_views():
		v = is_supported_view(view)
		if v:
			views.append(v)

	return views

def supported_files():
	"Returns list of opened files with given syntaxes"
	return [file_name(sv['view']) for sv in supported_views()]

def is_supported_view(view, strict=False):
	"Check if given view matches given syntax"

	# detecting syntax by scope selector isn't always a good idea:
	# sometimes users accidentally pick wrong syntax, for example,
	# CSS for .less files, Sass for .scss file. So if this is not an untitled 
	# file we're editing, use file extension to resolve syntax
	m = re.search(r'\.(css|less|scss)$', file_name(view))
	found_syntax = None
	if m:
		found_syntax = m.group(1)
	else:
		for syntax in supported_syntaxes:
			sel = selector_setting(syntax)
			if not sel:
				continue
			if not view.file_name() and not strict:
				# For new files, check if current scope is text.plain (just created)
				# or it's a strict syntax check
				sel = '%s, text.plain' % sel

			if view.score_selector(0, sel) > 0:
				found_syntax = syntax
				break
				
	if found_syntax:
		return {
			'view': view,
			'syntax': found_syntax
		}


def view_syntax(view):
	"Returns LiveStyle-supported syntax for given view"
	sv = is_supported_view(view)
	return  sv and sv['syntax'] or 'css'

def payload(view, data=None):
	"Returns diff/patch payload for given view"
	cn = content(view)
	syntax = view_syntax(view)

	result = {
		'uri':     file_name(view),
		'syntax':  syntax,
		'content': cn,
		'hash':    hash(cn),
	}

	global_deps = []
	try:
		global_deps = get_global_deps(view, syntax)
	except Exception as e:
		pass

	if global_deps:
		result['globalDependencies'] = global_deps

	if data:
		result.update(data)

	return result

def get_global_deps(view, syntax):
	"""
	Returns list of global dependencies defined in project
	preferences for given view.
	Currently works in Sublime Text 3 only
	"""
	# get global stylesheets defined in "livestyle/globals"
	# section of current project
	result = []

	if syntax == 'css':
		return result

	wnd = view.window()
	project_file = wnd.project_file_name()
	if not project_file or not wnd.project_data():
		return result

	project_base = os.path.dirname(project_file)
	deps = wnd.project_data().get('livestyle', {}).get('globals', [])
	# resolve globals: use only ones matched current syntax
	# and make paths absolute
	possible_ext = ['.%s' % syntax, '.css']
	for d in deps:
		if os.path.splitext(d)[1] not in possible_ext:
			continue

		d = os.path.expanduser(d)
		if not os.path.isabs(d):
			d = os.path.join(project_base, d)

		result.append(d)
	return result

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
