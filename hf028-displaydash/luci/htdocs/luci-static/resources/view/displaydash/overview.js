'use strict';
'require view';
'require rpc';
'require uci';

var callStatus = rpc.declare({
	object: 'displaydash',
	method: 'status',
	expect: {}
});

function fmt(v, d) {
	return (v === undefined || v === null || v === '') ? (d || '-') : v;
}

return view.extend({
	load: function () {
		return Promise.all([callStatus(), uci.load('displaydash')]);
	},

	render: function (data) {
		var status = data[0] || {};
		var screenProfile = uci.get('displaydash', 'main', 'screen_profile');
		var sys = status.sys || {};
		var px = status.proxy || {};

		var rows = [
			[_('代理服务'), px.srv_ok === true ? _('运行中') : _('未运行')],
			[_('节点'), fmt(px.node_label, fmt(px.node_addr))],
			[_('出口 IP'), fmt(px.exit_ip)],
			[_('公网 IP'), fmt(px.public_ip)],
			[_('订阅名'), fmt(px.sub_name)],
			[_('订阅'), (px.manual_node ? _('手动节点') :
				(px.sub_refresh === 'fail' ? _('异常') : _('正常')))],
			[_('剩余流量'), (px.sub_remain_gb !== null && px.sub_remain_gb !== undefined) ?
				px.sub_remain_gb.toFixed(2) + ' G' : '-'],
			[_('到期'),
			 (px.sub_expire && px.sub_expire !== 'N/A') ?
				px.sub_expire : _('无期限')],
			[_('温度 / 内存'), fmt(sys.temp) + 'C / ' +
				(sys.mem_pct !== null && sys.mem_pct !== undefined ?
					(100 - sys.mem_pct).toFixed(0) + '%' : '-')],
			[_('负载'), fmt(sys.load_pct) + '%'],
			[_('在线人数'), fmt(sys.online)],
			[_('管理 IP'), fmt(sys.lan_ip)]
			,[_('当前使用主题'), fmt(screenProfile)]
		];

		var table = E('table', { 'class': 'table' });
		for (var i = 0; i < rows.length; i++) {
			var tr = E('tr', { 'class': 'tr' });
			tr.appendChild(E('td', { 'class': 'td left' }, rows[i][0]));
			tr.appendChild(E('td', { 'class': 'td left' }, rows[i][1]));
			table.appendChild(tr);
		}

		return E('div', [
			E('h2', _('DisplayDash 总览')),
			table
		]);
	}
});
