'use strict';

const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(
  path.join(__dirname, 'luci', 'htdocs', 'luci-static', 'resources', 'view',
            'displaydash', 'subscription.js'), 'utf8');

const rootNode = { children: [] };
rootNode.appendChild = child => rootNode.children.push(child);
function makeNode(tag, attrs, children) {
  const rawChildren = children == null ? [] :
    (Array.isArray(children) ? children : [children]);
  const node = { tag, attrs: attrs || {}, children: rawChildren.flat() };
  node.appendChild = child => node.children.push(child);
  return node;
}

const uciData = {};
uciData.displaydash = {
  legacy: {
    '.name': 'legacy', '.type': 'sub',
    'url_match': 'one.example/token'
  }
};
const uci = {
  load: () => Promise.resolve(),
  sections: (config, type) => Object.keys(uciData[config] || {})
    .filter(sid => !type || uciData[config][sid]['.type'] === type)
    .map(sid => uciData[config][sid]),
  get: (config, sid, option) => (uciData[config] || {})[sid]?.[option] ?? null,
  add: (config, type) => {
    const sid = `sub${Object.keys(uciData[config] || {}).length + 1}`;
    uciData[config] = uciData[config] || {};
    uciData[config][sid] = { '.name': sid, '.type': type };
    return sid;
  },
  set: (config, sid, option, value) => {
    uciData[config][sid][option] = value;
  },
  save: () => Promise.resolve()
};

const urls = [
  'https://one.example/token#First Sub',
  'https://two.example/token#Second Sub'
];

uciData.homeproxy = {
  subscription: {
    '.name': 'subscription', '.type': 'homeproxy',
    'subscription_url': urls
  }
};

const rpc = { declare: () => () => Promise.resolve({ urls: urls }) };
const maps = [];

function Option(map, section, option, title) {
  this.map = map;
  this.section = section;
  this.option = option;
  this.title = title;
  this.values = [];
}
Option.prototype.value = function(value, title) { this.values.push([value, title]); };

function Section(map, sid, type, title) {
  this.map = map;
  this.sid = sid;
  this.type = type;
  this.title = title;
  this.options = [];
}
Section.prototype.option = function(cls, option, title) {
  const opt = new Option(this.map, this, option, title);
  this.options.push(opt);
  return opt;
};

const form = {
  Map: function(config, title, desc) {
    this.config = config; this.title = title; this.desc = desc; this.sections = [];
    maps.push(this);
  },
  NamedSection: Section,
  Value: Option,
  ListValue: Option
};
form.Map.prototype.section = function(cls, sid, type, title) {
  const sec = new Section(this, sid, type, title);
  this.sections.push(sec);
  return sec;
};
form.Map.prototype.render = function() {
  return Promise.resolve(makeNode('form'));
};

function _(value) { return value; }
function E(tag, attrs, children) { return makeNode(tag, attrs, children); }

const view = { extend: def => def };
const window = { location: { search: '' } };

(async () => {
  const def = new Function('view', 'uci', 'rpc', 'form', '_', 'E', 'window',
    `${source};`) (view, uci, rpc, form, _, E, window);
  const loaded = await def.load();
  console.log(JSON.stringify({ loadedType: typeof loaded, uciData }));
  console.log('has-source-currentUrls=' + source.includes('var currentUrls'));
  const result = await def.render();
  console.log(JSON.stringify({ mapsCount: maps.length }));
  const hasError = JSON.stringify(result).includes('未在 HomeProxy 配置中找到订阅链接');
  if (hasError || maps.length !== 1 || !maps[0].sections.length)
    throw new Error(`subscription view did not render: maps=${maps.length}`);
  if (maps[0].title !== 'First Sub' || maps[0].sections.length !== 1 ||
      maps[0].sections[0].sid !== 'legacy' ||
      Object.keys(uciData.displaydash).length !== 2)
    throw new Error(`unexpected first subscription: ${maps[0].title}`);

  function findNode(node, predicate) {
    if (!node || typeof node !== 'object') return null;
    if (predicate(node)) return node;
    for (const child of node.children || []) {
      const found = findNode(child, predicate);
      if (found) return found;
    }
    return null;
  }

  const selector = findNode(result, node =>
    node.attrs && node.attrs.id === 'displaydash-subscription-select');
  if (!selector || selector.children.length !== 2 ||
      selector.children[0].attrs.value !== urls[0] ||
      selector.children[1].attrs.value !== urls[1])
    throw new Error('subscription dropdown did not include HomeProxy URLs');

  const optionNames = maps[0].sections[0].options.map(option => option.option);
  for (const name of [
    'sub_url', 'url_match', 'sub_refresh_sec',
    'reset_style', 'sub_name_manual', 'sub_total_manual',
    'sub_used_manual', 'sub_expire_manual'
  ]) {
    if (!optionNames.includes(name))
      throw new Error(`missing per-subscription option: ${name}`);
  }
  if (optionNames.includes('subscription_ua'))
    throw new Error('subscription UA option should be hidden');
  const resetOption = maps[0].sections[0].options.find(option =>
    option.option === 'reset_style');
  if (!resetOption || !resetOption.values.some(value =>
      value[0] === 'month_start' && value[1] === '每月第一天'))
    throw new Error('month-start reset option is missing');
  console.log(JSON.stringify({ maps: maps.length, title: maps[0].title, ok: true }));
})().catch(error => {
  console.error(error);
  process.exit(1);
});
