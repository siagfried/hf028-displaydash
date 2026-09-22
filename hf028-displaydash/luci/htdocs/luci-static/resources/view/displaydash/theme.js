'use strict';
'require view';
'require uci';
'require form';

function getProfiles() {
	return uci.sections('displaydash-screen', 'screen').map(function (sec) {
		return {
			sid: sec['.name'],
			name: sec.profile_name || sec['.name']
		};
	});
}

function addNumber(option, min, max) {
	option.datatype = 'range(' + min + ',' + max + ')';
}

return view.extend({
	load: function () {
		return Promise.all([
			uci.load('displaydash'),
			uci.load('displaydash-screen')
		]);
	},

	render: function () {
		var profiles = getProfiles();
		var currentName = uci.get('displaydash', 'main', 'screen_profile') || '';
		var params = new URLSearchParams(window.location.search);
		var requested = params.get('profile');
		var current = profiles.find(function (p) {
			return p.name === requested;
		}) || profiles.find(function (p) {
			return p.name === currentName;
		}) || profiles[0];

		if (!current)
			return E('div', { 'class': 'cbi-map' }, [
				E('h2', _('主题')),
				E('p', _('未找到屏幕配置文件，请先在 /etc/config/displaydash-screen 中添加。'))
			]);

		var select = E('select', {
			'class': 'cbi-input-select',
			'id': 'displaydash-theme-select'
		}, profiles.map(function (p) {
			return E('option', { 'value': p.name }, p.name);
		}));
		select.value = current.name;
		select.addEventListener('change', function () {
			uci.set('displaydash', 'main', 'screen_profile', select.value);
			uci.save().then(function () {
				return uci.apply();
			}).then(function () {
				window.location.search = '?profile=' + encodeURIComponent(select.value);
			});
		});

		var header = E('div', { 'class': 'cbi-section' }, [
			E('div', { 'class': 'cbi-value' }, [
				E('label', { 'class': 'cbi-value-title', 'for': select.id }, _('当前主题')),
				E('div', { 'class': 'cbi-value-field' }, select)
			]),
			E('p', { 'class': 'cbi-section-descr' },
			_('控件映射和页面编号直接维护配置文件；以下是所有屏幕主题共用的显示与二维码设置。'))
		]);

		/* These options are global and intentionally live in displaydash.main,
		 * so changing the selected screen profile does not change them. */
		var map = new form.Map('displaydash', _('DisplayDash 主题'),
			_('主题文件只维护控件映射；以下参数对所有屏幕配置通用。'));
		var section = map.section(form.NamedSection, 'main', 'main',
			_('通用显示与二维码 / Common display and QR settings'));

		var direction = section.option(form.ListValue, 'direction', _('显示方向'));
		direction.value('1', _('1：180°'));
		direction.value('3', _('3：原方向'));

		var day = section.option(form.Value, 'brightness_day', _('白天亮度(%)'));
		addNumber(day, 0, 100);
		var night = section.option(form.Value, 'brightness_night', _('夜间亮度(%)'));
		addNumber(night, 0, 100);
		var logo = section.option(form.Value, 'backlight_logo', _('Logo 亮度(%)'));
		addNumber(logo, 0, 100);
		var dayStart = section.option(form.Value, 'day_start_hour', _('白天开始(小时)'));
		addNumber(dayStart, 0, 23);
		var nightStart = section.option(form.Value, 'night_start_hour', _('夜间开始(小时)'));
		addNumber(nightStart, 0, 23);

		section.option(form.Flag, 'qr_enable', _('显示 WiFi 二维码'));
		section.option(form.Value, 'qr_ssid', _('WiFi SSID'));
		var password = section.option(form.Value, 'qr_password', _('WiFi 密码'));
		password.password = true;

	return map.render().then(function (node) {
		var root = E('div', [E('h2', _('DisplayDash 主题')), header, node]);
		return root;
	});
	}
});
