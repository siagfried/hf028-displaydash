'use strict';
'require view';
'require uci';
'require form';

var currentUrls;

function subLabel(url) {
	var frag = (url || '').split('#')[1] || '';
	if (frag) {
		try { return decodeURIComponent(frag); } catch (e) { return frag; }
	}
	var m = /^[a-z]+:\/\/([^\/]+)/.exec(url || '');
	return m ? m[1] : _('未知订阅');
}

function sectionUrl(s) {
	return uci.get('displaydash', s, 'sub_url') ||
		uci.get('displaydash', s, 'url_match') || '';
}

function findSection(url) {
	var sections = uci.sections('displaydash', 'sub');

	for (var i = 0; i < sections.length; i++) {
		var configured = sectionUrl(sections[i]['.name']);
		if (configured && (configured === url || url.indexOf(configured) >= 0))
			return sections[i]['.name'];
	}

	return null;
}

function homeProxyUrls() {
	var urls = [];

		uci.sections('homeproxy', 'homeproxy').forEach(function (s) {
			var values = uci.get('homeproxy', s['.name'], 'subscription_url') || [];
		if (!Array.isArray(values))
			values = [values];
		values.forEach(function (value) {
			value = String(value || '').trim();
			if (value && urls.indexOf(value) < 0)
				urls.push(value);
		});
	});

	return urls;
}

function subItems(urls) {
	urls = urls || [];
	var params = new URLSearchParams(window.location.search);
	var wanted = params.get('url');

	var items = urls.map(function (url) {
		var sec = findSection(url);
		return {
			url: url,
			sec: sec,
			label: (sec && uci.get('displaydash', sec, 'sub_name_manual')) ||
				subLabel(url)
		};
	}).filter(function (item) {
		return item.sec;
	});

	if (wanted)
		for (var i = 0; i < items.length; i++)
			if (items[i].url === wanted) {
				items.unshift(items.splice(i, 1)[0]);
				break;
			}

	return items;
}

return view.extend({
	load: function () {
		return Promise.all([ uci.load('displaydash'), uci.load('homeproxy') ])
			.then(function () {
				var urls = homeProxyUrls();
				currentUrls = urls;
				var changed = false;

				if (!urls.length) {
					uci.sections('displaydash', 'sub').forEach(function (s) {
						var sid = s['.name'];
						var u = uci.get('displaydash', sid, 'sub_url') ||
								uci.get('displaydash', sid, 'url_match') || '';
						if (/^https?:\/\//i.test(u) && urls.indexOf(u) < 0)
							urls.push(u);
					});
				}

				urls.forEach(function (u) {
					if (findSection(u))
						return;
					var name = uci.add('displaydash', 'sub');
					uci.set('displaydash', name, 'sub_url', u);
					uci.set('displaydash', name, 'url_match', u);
					uci.set('displaydash', name, 'sub_refresh_sec', '3600');
									uci.set('displaydash', name, 'reset_style', 'month_start');
					changed = true;
				});

				if (changed)
					return uci.save('displaydash').then(function () {
						return uci.load('displaydash');
					});
				return Promise.resolve();
			});
	},

	render: function () {
		var root = E('div');
		var items = subItems(currentUrls);

		if (!items.length) {
			root.appendChild(E('p', _('未在 HomeProxy 配置中找到订阅链接，'
				+ '请先在代理设置中添加。')));
			return root;
		}

		var current = items[0];
		var select = E('select', {
			'id': 'displaydash-subscription-select',
			'class': 'cbi-input-select'
		}, items.map(function (item) {
			return E('option', { 'value': item.url }, item.label);
		}));
		select.value = current.url;
		select.onchange = function (ev) {
			window.location.search = '?url=' +
				encodeURIComponent(ev.target.value);
		};
		root.appendChild(E('div', { 'class': 'cbi-section' }, [
			E('div', { 'class': 'cbi-section-descr' },
				_('从 HomeProxy 配置中选择订阅；下面的参数只作用于当前订阅。')),
			E('label', { 'for': 'displaydash-subscription-select' },
				_('当前订阅')),
			select
		]));

		var m = new form.Map('displaydash', current.label,
			_('所有参数按订阅分别保存，切换订阅后可独立修改。'));
		var s = m.section(form.NamedSection, current.sec, 'sub', current.label);
		s.option(form.Value, 'sub_url', _('订阅 URL（只读）')).readonly = true;
		s.option(form.Value, 'url_match', _('订阅 URL 片段'));
		var rt = s.option(form.Value, 'sub_refresh_sec', _('刷新时间(秒)'));
		rt.datatype = 'uinteger';
		var reset = s.option(form.ListValue, 'reset_style',
			_('无重置信息时的推算方式'));
		reset.value('expire_day', _('到期日的每月同日（有到期日时默认）'));
		reset.value('month_start', _('每月第一天'));
		s.option(form.Value, 'sub_name_manual', _('自定订阅显示名'));
		var total = s.option(form.Value, 'sub_total_manual', _('总流量(GB)'));
		total.datatype = 'ufloat';
		var used = s.option(form.Value, 'sub_used_manual', _('已用流量(GB)'));
		used.datatype = 'ufloat';
		var expire = s.option(form.Value, 'sub_expire_manual',
			_('到期日期(YYYY-MM-DD)'));
		expire.validate = function (sectionId, value) {
			return !value || /^\d{4}-\d{2}-\d{2}$/.test(value) ?
				true : _('日期格式必须为 YYYY-MM-DD');
		};

		return m.render().then(function (node) {
			root.appendChild(node);
			return root;
		});
	}
});
