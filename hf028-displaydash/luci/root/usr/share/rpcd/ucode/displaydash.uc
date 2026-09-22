'use strict';

import { readfile } from 'fs';
import { cursor } from 'uci';

function read_json(path, fallback) {
	let raw = readfile(path);
	if (raw === null || raw === '')
		return fallback;
	try {
		return json(raw);
	} catch (e) {
		return fallback;
	}
}

const methods = {};

methods.subscriptions = {
	call: function (args) {
		const uci = cursor();
		let urls = [];

		/* HomeProxy uses config homeproxy 'subscription'; the section type is
		 * homeproxy, so filtering by subscription would silently return none. */
		uci.foreach('homeproxy', 'homeproxy', (sec) => {
			let values = sec?.subscription_url ?? [];

			if (type(values) != 'array')
				values = [ values ];

			for (let value in values) {
				const url = trim(value);
				let exists = false;

				for (let current in urls)
					exists = exists || current == url;

				if (url && !exists)
					push(urls, url);
			}
		});

		return { urls: urls };
	}
};

methods.status = {
	call: function (args) {
		let sys = read_json('/tmp/displaydash/sys.json', {});
		let px = read_json('/tmp/displaydash/proxy.json', {});
		return { sys: sys, proxy: px };
	}
};

return { 'displaydash': methods };
