!function(e){if("object"==typeof exports&&"undefined"!=typeof module)module.exports=e();else if("function"==typeof define&&define.amd)define([],e);else{var f;"undefined"!=typeof window?f=window:"undefined"!=typeof global?f=global:"undefined"!=typeof self&&(f=self),f.livestyleClient=e()}}(function(){var define,module,exports;return (function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);var f=new Error("Cannot find module '"+o+"'");throw f.code="MODULE_NOT_FOUND",f}var l=n[o]={exports:{}};t[o][0].call(l.exports,function(e){var n=t[o][1][e];return s(n?n:e)},l,l.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
var client = require('livestyle-client');
var patcher = require('livestyle-cssom-patcher');

function enabled() {
	var elem = document && document.documentElement;
	return !elem || elem.getAttribute('data-livestyle-extension') !== 'available';
}

function extractHost(url) {
	if (url) {
		var m = url.match(/^(\w+)(:\/\/.+?)(\/|$)/);
		return m && (/^wss?$/.test(m[1]) ? m[1] : 'ws') + m[2];
	}
}

function initFromScript(script) {
	var hosts = [
		client.config().host,
		extractHost(script.src),
		extractHost(script.getAttribute('data-livestyle-host'))
	];
	init({
		rewriteHost: true,
		host: hosts.filter(function(host) {
			return !!host;
		})
	});
}

function init(config) {
	client
	.on('open', function() {
		console.log('LiveStyle: connected to server');
	})
	.on('close', function() {
		console.log('LiveStyle: closed connection to server');
	})
	.on('incoming-updates', function(data) {
		// console.log('incoming patch', data.uri, data.patches);
		if (!enabled()) {
			return;
		}
		var result = patcher.patch(data.uri, data.patches);
		if (!result && config.rewriteHost) {
			// Unable to patch CSS, might be due to host mismatch.
			// One of the possible reason: viewing the same local page
			// on native browser and in virtual machine.
			var uri = data.uri.replace(/^\w+:\/\/[^\/]+/, location.protocol + '//' + location.host);
			if (uri !== data.uri) {
				patcher.patch(uri, data.patches);
			}
		}
	})
	.connect(config);
}


// find script tag that embedded client
var scripts = document.getElementsByTagName('script');
var inited = false;
for (var i = 0, il = scripts.length; i < il; i++) {
	if (~scripts[i].src.indexOf('livestyle-client.js')) {
		inited = true;
		initFromScript(scripts[i]);
		break;
	}
}

if (!inited) {
	init();
}

module.exports = {
	disconnect: function() {
		client.disconnect();
	}
};
},{"livestyle-client":2,"livestyle-cssom-patcher":4}],2:[function(require,module,exports){
if (typeof module === 'object' && typeof define !== 'function') {
	var define = function (factory) {
		module.exports = factory(require, exports, module);
	};
}

define(function(require, exports, module) {
	var eventMixin = require('./lib/eventMixin');

	var defaultConfig = {
		host: 'ws://127.0.0.1:54000',
		timeout: 2000,
		endpoint: '/livestyle'
	};
	
	var STATUS_IDLE = 'idle';
	var STATUS_CONNECTING = 'connecting';
	var STATUS_CONNECTED = 'connected';

	var sock = null;
	var _timer;
	var retry = true;
	var status = STATUS_IDLE;

	function extend(obj) {
		for (var i = 1, il = arguments.length, src; i < il; i++) {
			src = arguments[i];
			src && Object.keys(src).forEach(function(key) {
				obj[key] = src[key];
			});
		}
		return obj;
	}

	function createSocket(url, callback) {
		var s = new WebSocket(url);
		s.onclose = function() {
			if (status !== STATUS_CONNECTED && callback) {
				// cannot establish initial connection
				callback();
			}
		};

		s.onopen = function() {
			callback(s);
		};
	}

	function connect(config, callback) {
		config = extend({}, defaultConfig, config || {});
		status = STATUS_CONNECTING;
		sock = null;

		if (_timer) {
			clearTimeout(_timer);
			_timer = null;
		}

		// create pool of urls we should try before
		// restarting connection sequence
		var urls = (Array.isArray(config.host) ? config.host : [config.host]).map(function(url) {
			return url + config.endpoint;
		});

		var _connect = function() {
			if (!urls.length) {
				return reconnect(config);
			}

			createSocket(urls.shift(), function(s) {
				if (s) {
					// connection established
					sock = s;
					status = STATUS_CONNECTED;
					callback && callback(true, s);
					module.emit('open');

					s.onclose = function() {
						sock = null;
						module.emit('close');
						reconnect(config);
					};

					s.onmessage = handleMessage;
					s.onerror = handleError;
				} else {
					// no connection, try next url
					module.emit('close');
					_connect();
				}
			});
		};
		_connect();
	}

	function reconnect(config, callback) {
		if (config.timeout && retry) {
			_timer = setTimeout(connect, config.timeout, config, callback);
		} else {
			status = STATUS_IDLE;
		}
	}

	function handleMessage(evt) {
		var payload = typeof evt.data === 'string' ? JSON.parse(evt.data) : evt.data;
		module.emit('message-receive', payload.name, payload.data);
		module.emit(payload.name, payload.data);
	}

	function handleError(e) {
		module.emit('error', e);
	}

	var module = {
		config: function(data) {
			if (typeof data === 'object') {
				extend(defaultConfig, data);
			}
			return defaultConfig;
		},
		
		/**
		 * Establishes connection to server
		 * @param {Object} config Optional connection config
		 * @param {Function} callback A function called with connection status
		 */
		connect: function(config, callback) {
			if (typeof config === 'function') {
				callback = config;
				config = {};
			}

			if (status === STATUS_IDLE) {
				retry = true;
				connect(config, callback);
			} else if (status === STATUS_CONNECTED && callback) {
				callback(true, sock);
			}

			return this;
		},

		/**
		 * Drop connection to server
		 */
		disconnect: function() {
			if (this.connected) {
				retry = false;
				status = STATUS_IDLE;
				sock.close();
			}
			return this;
		},

		/**
		 * Sends given message to socket server
		 * @param  {String} message
		 */
		send: function(name, data) {
			if (this.connected) {
				module.emit('message-send', name, data);
				sock.send(JSON.stringify({
					name: name,
					data: data
				}));
			}
			return this;
		}
	};

	Object.defineProperty(module, 'connected', {
		enumerable: true,
		get: function() {
			return status === STATUS_CONNECTED;
		}
	});

	return extend(module, eventMixin);
});
},{"./lib/eventMixin":3}],3:[function(require,module,exports){
/**
 * A simple event dispatcher mixin, borrowed from Backbone.Event.
 * Users should extend their objects/modules with this mixin.
 * @example
 * define(['lodash', 'eventMixin'], function(_, eventMixin) {
 * 	return _.extend({
 * 		...
 * 	}, eventMixin);
 * })
 */
if (typeof module === 'object' && typeof define !== 'function') {
	var define = function (factory) {
		module.exports = factory(require, exports, module);
	};
}

define(function(require, exports, module) {
	// Regular expression used to split event strings
	var eventSplitter = /\s+/;
	
	  // Create a local reference to slice/splice.
	  var slice = Array.prototype.slice;
	
	return {
		/**
		 * Bind one or more space separated events, `events`, to a `callback`
		 * function. Passing `"all"` will bind the callback to all events fired.
		 * @param {String} events
		 * @param {Function} callback
		 * @param {Object} context
		 * @memberOf eventDispatcher
		 */
		on: function(events, callback, context) {
			var calls, event, node, tail, list;
			if (!callback)
				return this;
			
			events = events.split(eventSplitter);
			calls = this._callbacks || (this._callbacks = {});

			// Create an immutable callback list, allowing traversal during
			// modification.  The tail is an empty object that will always be used
			// as the next node.
			while (event = events.shift()) {
				list = calls[event];
				node = list ? list.tail : {};
				node.next = tail = {};
				node.context = context;
				node.callback = callback;
				calls[event] = {
					tail : tail,
					next : list ? list.next : node
				};
			}

			return this;
		},

		/**
		 * Remove one or many callbacks. If `context` is null, removes all
		 * callbacks with that function. If `callback` is null, removes all
		 * callbacks for the event. If `events` is null, removes all bound
		 * callbacks for all events.
		 * @param {String} events
		 * @param {Function} callback
		 * @param {Object} context
		 */
		off: function(events, callback, context) {
			var event, calls, node, tail, cb, ctx;

			// No events, or removing *all* events.
			if (!(calls = this._callbacks))
				return;
			if (!(events || callback || context)) {
				delete this._callbacks;
				return this;
			}

			// Loop through the listed events and contexts, splicing them out of the
			// linked list of callbacks if appropriate.
			events = events ? events.split(eventSplitter) : _.keys(calls);
			while (event = events.shift()) {
				node = calls[event];
				delete calls[event];
				if (!node || !(callback || context))
					continue;
				// Create a new list, omitting the indicated callbacks.
				tail = node.tail;
				while ((node = node.next) !== tail) {
					cb = node.callback;
					ctx = node.context;
					if ((callback && cb !== callback) || (context && ctx !== context)) {
						this.on(event, cb, ctx);
					}
				}
			}

			return this;
		},
		
		/**
		 * Trigger one or many events, firing all bound callbacks. Callbacks are
		 * passed the same arguments as `trigger` is, apart from the event name
		 * (unless you're listening on `"all"`, which will cause your callback
		 * to receive the true name of the event as the first argument).
		 * @param {String} events
		 */
		emit: function(events) {
			var event, node, calls, tail, args, all, rest;
			if (!(calls = this._callbacks))
				return this;
			all = calls.all;
			events = events.split(eventSplitter);
			rest = slice.call(arguments, 1);

			// For each event, walk through the linked list of callbacks twice,
			// first to trigger the event, then to trigger any `"all"` callbacks.
			while (event = events.shift()) {
				if (node = calls[event]) {
					tail = node.tail;
					while ((node = node.next) !== tail) {
						node.callback.apply(node.context || this, rest);
					}
				}
				if (node = all) {
					tail = node.tail;
					args = [ event ].concat(rest);
					while ((node = node.next) !== tail) {
						node.callback.apply(node.context || this, args);
					}
				}
			}

			return this;
		}
	};
});
},{}],4:[function(require,module,exports){
/**
 * CSSOM LiveStyle patcher: maps incoming updates to browser’s 
 * CSS Object Model. This is a very fast method of applying 
 * incoming updates from LiveStyle which is also works in any
 * modern browser environment.
 */
if (typeof module === 'object' && typeof define !== 'function') {
	var define = function (factory) {
		module.exports = factory(require, exports, module);
	};
}

define(function(require, exports, module) {
	var pathfinder = require('livestyle-pathfinder');

	/**
	 * Node path shim
	 */
	function NodePath(path) {
		if (Array.isArray(path)) {
			this.components = path.map(NodePathComponent);
		} else {
			this.components = [];
		}
	}

	NodePath.prototype.toString = function() {
		return this.components.map(function(c) {
			return c.toString(true);
		}).join('/');
	};

	function NodePathComponent(name, pos) {
		if (!(this instanceof NodePathComponent)) {
			return new NodePathComponent(name, pos);
		}

		if (Array.isArray(name)) {
			pos = name[1];
			name = name[0];
		}

		this.name = normalizeSelector(name);
		this.pos = pos || 1;
	}

	NodePathComponent.prototype.toString = function() {
		return this.name +  (this.pos > 1 ? '|' + this.pos : '');
	};

	function normalizeSelector(sel) {
		return sel.trim().replace(/:+(before|after)$/, '::$1');
	}

	/**
	 * Findes all stylesheets in given context, including
	 * nested `@import`s
	 * @param  {StyleSheetList} ctx List of stylesheets to scan
	 * @return {Object} Hash where key as a stylesheet URL and value
	 * is a stylesheet reference
	 */
	function findStyleSheets(ctx, out) {
		out = out || {};
		for (var i = 0, il = ctx.length, url, item; i < il; i++) {
			item = ctx[i];
			url = item.href;
			if (url in out) {
				// stylesheet already added
				continue;
			}

			out[url] = item;
			
			// find @import rules
			if (item.cssRules) {
				for (var j = 0, jl = item.cssRules.length; j < jl; j++) {
					if (item.cssRules[j].type == 3) {
						findStyleSheets([item.cssRules[j].styleSheet], out);
					}
				}
			}
		}
		
		return out;
	}

	function atRuleName(rule) {
		/*
		 * Reference:
		 * UNKNOWN_RULE: 0
		 * STYLE_RULE: 1
		 * CHARSET_RULE: 2
		 * IMPORT_RULE: 3
		 * MEDIA_RULE: 4
		 * FONT_FACE_RULE: 5
		 * PAGE_RULE: 6
		 * KEYFRAMES_RULE: 7
		 * KEYFRAME_RULE: 8
		 * SUPPORTS_RULE: 12
		 * WEBKIT_FILTER_RULE: 17
		 * HOST_RULE: 1001
		 */
		switch (rule.type) {
			case 2: return '@charset';
			case 3: return '@import';
			case 4: return '@media ' + rule.media.mediaText;
			case 5: return '@font-face';
		}
	}

	/**
	 * Returns name of given rule
	 * @param  {CSSRule} rule
	 * @return {String}
	 */
	function ruleName(rule) {
		var sel = rule.selectorText || atRuleName(rule);
		if (sel) {
			return sel;
		}

		var text = rule.cssText;
		if (text) {
			return (text.split('{', 2)[0] || '').trim();
		}
	}

	/**
	 * Returns rule’s parent (stylesheet or rule)
	 * @param  {CSSRule} rule
	 * @return {CSSStyleSheet}
	 */
	function parent(rule) {
		return rule.parentRule || rule.parentStyleSheet;
	}

	/**
	 * Check if given @-rule equals to given patch property
	 * @param  {CSSRule} rule
	 * @param  {Object}  prop
	 * @return {Boolean}
	 */
	function atRuleEquals(rule, prop) {
		if (atRuleName(rule) !== prop.name) {
			return false;
		}

		switch (prop.name) {
			case '@charset':
				return rule.encoding === prop.value.trim().replace(/^['"]|['"]$/g, '');
			case '@import':
				return rule.href === prop.value.trim().replace(/^url\(['"]?|['"]?\)$/g, '');
		}
	}

	/**
	 * Updates given rule with data from patch
	 * @param  {CSSRule} rule
	 * @param  {Array} patch
	 */
	function patchRule(rule, patch) {
		if (!rule) {
			// not a CSSStyleRule, aborting
			return;
		}

		var reAt = /^@/, childRule;

		// remove properties
		patch.remove.forEach(function(prop) {
			if (reAt.test(prop)) {
				// @-properties are not properties but rules
				if (!rule.cssRules || !rule.cssRules.length) {
					return;
				}
				
				for (var i = 0, il = rule.cssRules.length; i < il; i++) {
					if (atRuleEquals(rule.cssRules[i], prop)) {
						return rule.deleteRule(i);
					}
				}
			} else if (rule.style) {
				rule.style.removeProperty(prop.name);
			}
		});

		var updateRules = {
			'@charset': [],
			'@import': []
		};

		// update properties on current rule
		var properties = patch.update.map(function(prop) {
			if (prop.name in updateRules) {
				updateRules[prop.name].push(prop);
				return '';
			}

			return prop.name + ':' + prop.value + ';';
		}).join('');

		if (rule.style) {
			rule.style.cssText += properties;
		}

		// insert @-properties as rules
		while (childRule = updateRules['@charset'].pop()) {
			rule.insertRule(childRule.name + ' ' + childRule.value, 0);
		}

		if (updateRules['@import'].length && rule.cssRules) {
			// @import’s must be inserted right after existing imports
			var childIx = 0, childName;
			for (var i = rule.cssRules.length - 1; i >= 0; i--) {
				childName = atRuleName(rule.cssRules[i]);
				if (childName === '@charset' || childName === '@import') {
					childIx = i;
					break;
				}
			}

			while (childRule = updateRules['@import'].pop()) {
				rule.insertRule(childRule.name + ' ' + childRule.value, childIx);
			}
		}
	}

	function setupFromPartialMatch(match) {
		// The `rest` property means we didn’t found exact section
		// where patch should be applied, but some of its parents.
		// In this case we have to re-create the `rest` sections
		// in best matching parent
		var accumulated = match.rest.reduceRight(function(prev, cur) {
			return cur.name + ' {' + prev + '}';
		}, '');

		var parent = match.parent;
		var insertIndex = parent.ref.cssRules ? parent.ref.cssRules.length : 0;
		if (match.node) {
			insertIndex = match.node.ix;
		}

		// console.log('Insert rule at index', insertIndex, match);
		try {
			var ix = parent.ref.insertRule(accumulated, insertIndex);
		} catch (e) {
			console.warn('LiveStyle:', e.message);
			return;
		}

		var ctx = parent.ref.cssRules[ix];
		var indexed = exports.createIndex(ctx);
		indexed.name = ruleName(ctx);
		indexed.ix = ix;
		parent.children.splice(match.index, 0, indexed);
		for (var i = match.index + 1, il = parent.children.length; i < il; i++) {
			parent.children[i].ix++;
		}

		while (ctx.cssRules && ctx.cssRules.length) {
			ctx = ctx.cssRules[0];
		}

		return ctx;
	}

	function deleteRuleFromMatch(match) {
		try {
			parent(match.node.ref).deleteRule(match.node.ix);
		} catch (e) {
			console.warn('LiveStyle:', e);
			console.warn(match);
		}
		// console.log('Removed rule at index', match.node.ix);
		var ix = match.parent.children.indexOf(match.node);
		if (~ix) {
			match.parent.children.splice(ix, 1);
			for (var i = ix, il = match.parent.children.length, child; i < il; i++) {
				match.parent.children[i].ix--;
			}
		}
	}

	function normalizeHints(hints) {
		return hints.map(function(hint) {
			if (hint.before) {
				hint.before = hint.before.map(NodePathComponent);
			}
			if (hint.after) {
				hint.after = hint.after.map(NodePathComponent);
			}
			return hint;
		});
	}

	/**
	 * Returns hash with available stylesheets. The keys of hash
	 * are absolute urls and values are pointers to StyleSheet objects
	 * @return {Object}
	 */
	exports.stylesheets = function() {
		return findStyleSheets(document.styleSheets);
	};

	/**
	 * Updates given stylesheet with patches
	 * @param  {CSSStyleSheet} stylesheet
	 * @param  {Array} patches
	 * @returns {StyleSheet} Patched stylesheet on success,
	 * `false` if it’s impossible to apply patch on given 
	 * stylesheet.
	 */
	exports.patch = function(stylesheet, patches) {
		var self = this;
		if (typeof stylesheet === 'string') {
			stylesheet = this.stylesheets()[stylesheet];
		}

		if (!stylesheet || !stylesheet.cssRules) {
			return false;
		}


		var index = this.createIndex(stylesheet);
		if (!Array.isArray(patches)) {
			patches = [patches];
		}

		patches.forEach(function(patch) {
			var path = new NodePath(patch.path);
			var hints = patch.hints ? normalizeHints(patch.hints) : null;
			var location = pathfinder.find(index, path, hints);
			if (location.partial && patch.action === 'remove') {
				// node is absent, do nothing
				return;
			}

			if (!location.partial) {
				// exact match on node
				if (patch.action === 'remove') {
					return deleteRuleFromMatch(location);
				}
				return patchRule(location.node.ref, patch);
			}

			patchRule(setupFromPartialMatch(location), patch);
		});

		return stylesheet;
	};

	exports.createIndex = function(ctx, parent) {
		var indexOf = function(item) {
			return this.children.indexOf(item);
		};

		if (!parent) {
			parent = {
				ix: -1,
				name: '',
				parent: null,
				children: [],
				ref: ctx,
				indexOf: indexOf
			};
		}

		var rules = ctx.cssRules;
		if (!rules) {
			return parent;
		}

		for (var i = 0, il = rules.length, rule, name, item; i < il; i++) {
			rule = rules[i];
			name = ruleName(rule);
			if (name === '@charset' || name === '@import') {
				continue;
			}

			item = {
				ix: i,
				name: normalizeSelector(name),
				parent: parent,
				children: [],
				ref: rule,
				indexOf: indexOf
			};

			parent.children.push(item);
			this.createIndex(rule, item);
		}

		return parent;
	};

	return exports;
});
},{"livestyle-pathfinder":5}],5:[function(require,module,exports){
if (typeof module === 'object' && typeof define !== 'function') {
	var define = function (factory) {
		module.exports = factory(require, exports, module);
	};
}

define(function(require, exports, module) {
	function last(arr) {
		return arr[arr.length - 1];
	}

	function flatten(arr, ctx) {
		ctx = ctx || [];
		arr.forEach(function(item) {
			Array.isArray(item) ? flatten(item, ctx) : ctx.push(item);
		});
		return ctx;
	}

	function nodeName(node) {
		return node ? (node.normalName || node.name) : null;
	}

	function SearchResult(parent, index, rest) {
		this.parent = parent;
		this.index = index;
		this.partial = !!rest;
		this.rest = rest;
	}

	Object.defineProperty(SearchResult.prototype, 'node', {
		enumerabe: true,
		get: function() {
			if (typeof this.index === 'undefined') {
				return this.parent;
			}
			return this.parent.children[this.index];
		}
	});

	/**
	 * Locates child nodes inside `ctx` that matches given 
	 * path `component`. 
	 * @param  {ResolvedNode}      ctx       Node where to search
	 * @param  {NodePathComponent} component Path component to match
	 * @param  {Object} hint       Location hint
	 * @return {Array}  List of matched nodes, ordered by matching score
	 */
	function locate(ctx, component, hint) {
		var items = ctx.children.filter(function(child) {
			return nodeName(child) === component.name;
		});

		return items.map(function(node, i) {
			var score = 0;
			if (hint) {
				score += matchesBeforeHints(node, hint.before) ? 0.5 : 0;
				score += matchesAfterHints(node, hint.after) ? 0.5 : 0;
			} else if (i === component.pos - 1) {
				score += 0.1;
			}

			return {
				node: node,
				index: i,
				score: score
			};
		});
	}

	function matchesSort(a, b) {
		return (b.score * 10000 + b.index) - (a.score * 10000 + a.index);
	}

	function matchesBeforeHints(node, hints) {
		var siblings = node.parent.children;
		var ix = siblings.indexOf(node);

		if (!hints || hints.length - 1 > ix) {
			// more hints than siblings
			return false;
		}

		if (hints.length === ix === 0) {
			// hint tells it’s a first node
			return true;
		}

		for (var i = hints.length - 1, sibling; i >= 0; i--) {
			sibling = siblings[--ix];
			if (!sibling || nodeName(sibling) !== hints[i].name) {
				return false;
			}
		}

		return true;
	}

	function matchesAfterHints(node, hints) {
		var siblings = node.parent.children;
		var ix = siblings.indexOf(node);

		if (!hints || ix + hints.length > siblings.length - 1) {
			 // more hints than siblings
			return false;
		}

		if (hints.length === 0 && ix === siblings.length - 1) {
			// hint tells it’s a last node
			return true;
		}

		for (var i = 0, il = hints.length, sibling; i < il; i++) {
			sibling = siblings[++ix];
			if (!sibling || nodeName(sibling) !== hints[i].name) {
				return false;
			}
		}

		return true;
	}

	function matchingSet(items, hints) {
		var result = [];
		if (!hints || !hints.length) {
			return result;
		}

		var hl = hints.length;
		items.forEach(function(item, i) {
			if (hints[0].name === nodeName(item)) {
				for (var j = 1; j < hl; j++) {
					if (!items[i + j] || nodeName(items[i +j]) !== hints[j].name) {
						return false;
					}
				}
				result.push(i);
			}
		});

		return result;
	};

	return {
		/**
		 * Tries to find the best insertion point for absent
		 * path nodes (or its components).
		 * @param  {ResolvedNode} tree
		 * @param  {NodePath} path
		 * @param  {Object} hints
		 * @return {Object} Object with `parent` and `index` properties
		 * pointing to matched element. The `rest` property (if present)
		 * means given path can’t be fully matched and `index` propery
		 * points to `parent` child index where the `rest` node path
		 * components should be added
		 */
		find: function(tree, path, hints) {
			if (path.toString() === '') {
				// it’s a root node
				return new SearchResult(tree);
			}

			hints = (hints || []).slice(0);
			var ctx = [tree], found;
			var components = path.components.slice(0);
			var component, hint, result;

			while (component = components.shift()) {
				hint = hints.shift();
				found = flatten(ctx.map(function(node) {
					return locate(node, component, hint);
				})).sort(matchesSort);

				found = found.filter(function(item) {
					return item.score === found[0].score;
				}).map(function(item) {
					return item.node;
				});

				if (!found.length) {
					// Component wasn’t found, which means
					// we have to create it, as well as all other
					// descendants.
					// So let’s find best insertion position, 
					// according to given hints
					components.unshift(component);
					result = last(ctx);
					return new SearchResult(result, this.indexForHint(result, hint), components);
				} else {
					ctx = found;
				}
			}

			result = last(ctx);
			return new SearchResult(result.parent, result.parent.indexOf(result));
		},

		/**
		 * Returns best insertion position inside `parent`
		 * for given hint
		 * @param  {ResolvedNode} parent
		 * @param  {Object} hint
		 * @return {Number}
		 */
		indexForHint: function(parent, hint) {
			var items = parent.children;
			if (!hint) {
				return parent.children.length;
			}

			var before = matchingSet(items, hint.before).map(function(ix) {
				return ix + hint.before.length;
			});
			var after = matchingSet(items, hint.after);
			var possibleResults = [];
			if (hint.before.length && hint.after.length) {
				// we have both sets of hints, find index between them
				before.forEach(function(ix) {
					for (var i = 0, il = after.length; i < il; i++) {
						if (after[i] >= ix) {
							return possibleResults.push(after[i]);
						}
					}
				});
			} else if (hint.before.length) {
				possibleResults = before;
			} else if (hint.after.length) {
				possibleResults = after;
			}

			// insert nodes at the end by default
			return possibleResults.length ? possibleResults[0] : items.length;
		}
	};
});
},{}]},{},[1])(1)
});