'use strict';
'require view';
'require uci';
'require form';

return view.extend({
	load: function () {
		return uci.load('displaydash');
	},

	render: function () {
		var m, s, o;

		m = new form.Map('displaydash',
			_('DisplayDash 设置'),
			_('保存后约 2 秒内自动生效（服务热加载配置）；串口改动在服务重连后生效。'));

		/* 串口与屏幕 */
		s = m.section(form.NamedSection, 'main', 'main',
			_('串口与屏幕'));
		s.option(form.Value, 'instance', _('实例名'));
		s.option(form.Value, 'port', _('串口设备'));
		s.option(form.Value, 'baud', _('波特率')).datatype = 'uinteger';
		s.option(form.Value, 'refresh_sec', _('刷新间隔(秒)'));
		s.option(form.Value, 'boot_logo_sec', _('进度 Logo 停留(秒)'));
		s.option(form.Value, 'boot_prog_sec', _('进度条一圈(秒)'));
		s.option(form.Value, 'boot_logo_timeout', _('开机最久等待(秒)'));
		s.option(form.Value, 'boot_grace_sec', _('开机宽限期(秒)'));

		/* 采集与阈值 */
		s = m.section(form.NamedSection, 'main', 'main',
			_('检测与阈值'));
		s.option(form.Value, 'wan_iface', _('WAN 网口'));
		s.option(form.Value, 'public_ip', _('公网连通测试 IP'));
		s.option(form.Value, 'net_check_sec', _('网关/WAN 检测间隔(秒)'));
		s.option(form.Value, 'dns_check_sec', _('DNS 检测间隔(秒)'));
		s.option(form.Value, 'speed_switch', _('速率进位阈值'));
		s.option(form.Value, 'service_proc', _('代理进程名（空=自动）'));
		s.option(form.Value, 'srv_check_sec', _('代理进程检测间隔(秒)'));
		s.option(form.Value, 'node_check_sec', _('节点检测间隔(秒)'));
		s.option(form.Value, 'exit_retry_sec', _('出口重查间隔(秒)'));
		s.option(form.Value, 'google_check_sec', _('Google 检测间隔(秒)'));
		s.option(form.Value, 'google_url', _('翻墙检测 URL'));
		s.option(form.Value, 'google_ms', _('翻墙缓慢阈值(ms)'));
		s.option(form.Value, 'ap_ip', _('AP 地址'));
		s.option(form.Value, 'ap_user', _('AP 用户'));
		o = s.option(form.Value, 'ap_password', _('AP 密码'));
		o.password = true;
		s.option(form.Value, 'ap_check_sec', _('AP 检测间隔(秒)'));
		s.option(form.Value, 'ap_clients_check_sec', _('在线人数轮询(秒)'));
		s.option(form.Value, 'load_warn', _('负载警告%'));
		s.option(form.Value, 'load_fail', _('负载故障%'));
		s.option(form.Value, 'mem_warn', _('内存警告(可用%)'));
		s.option(form.Value, 'mem_fail', _('内存故障(可用%)'));
		s.option(form.Value, 'temp_warn', _('温度警告℃'));
		s.option(form.Value, 'temp_fail', _('温度故障℃'));
		s.option(form.Value, 'disk_warn', _('存储警告(可用%)'));
		s.option(form.Value, 'disk_fail', _('存储故障(可用%)'));

		return m.render();
	}
});
