type Row = Record<string, any>;
const esc = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
type Api = (path: string, body?: Row, method?: string) => Promise<any>;
type Deps = {state: Row; api: Api; modal: (title:string, body:string, ready?: (d:HTMLDialogElement)=>void)=>HTMLDialogElement; modalError:(e:unknown)=>void; load:()=>Promise<void>; render:()=>void; inform:(text:string)=>void};

type SettingsTab = 'overview' | 'models' | 'search' | 'data';
const settingsTabs: [SettingsTab, string][] = [
  ['overview', '概览'],
  ['models', 'AI 模型'],
  ['search', '搜索'],
  ['data', '数据与版本'],
];
export const settingsUI: {tab: SettingsTab} = {tab: 'overview'};

export function aiSettingsView(state: Row, modeText: string) {
  const ai = state.ai || {configs: [], default_model_config_id: null};
  const search = state.search_provider || {provider: 'tavily', configured: false, secret_status: 'not_configured', revision: 0};
  const secretLabel = (config: Row) => {
    if (!config.configured_ref) return '未设置 Key';
    if (config.secret_status === 'ready') return 'Key 已验证可用';
    if (config.secret_status === 'not_checked') return 'Key 已配置，尚未验证';
    const labels: Row = {missing: '缺失', denied: '访问被拒绝', locked: 'Keychain 已锁定', interaction_not_allowed: '不允许交互授权', timeout: '验证超时', error: '验证失败'};
    return `Key 状态：${labels[config.secret_status] || config.secret_status}`;
  };
  const rows = (ai.configs || []).map((config: Row) => `<article class="ai-config-row"><div><h3>${esc(config.display_name)}</h3><p>${esc(config.provider)} · ${esc(config.model)}</p><small>${esc(config.base_url)} · ${secretLabel(config)}${config.id === ai.default_model_config_id ? ' · 当前使用' : ''}</small></div><div class="actions"><button class="secondary" data-ai-test="${esc(config.id)}">测试</button>${config.id === ai.default_model_config_id ? '<span class="pill">当前使用</span>' : `<button class="quiet" data-ai-default="${esc(config.id)}">设为当前</button>`}<button class="quiet" data-ai-edit="${esc(config.id)}">编辑</button><button class="text-btn" data-ai-delete="${esc(config.id)}">删除</button></div></article>`).join('');
  const current = (ai.configs || []).find((config: Row) => config.id === ai.default_model_config_id);
  const searchStatus = search.secret_status === 'ready' ? 'Secret 已验证可读' : search.secret_status === 'not_checked' ? '已配置，尚未检查' : search.configured ? `状态：${esc(search.secret_status)}` : search.secret_status === 'not_configured' ? '尚未配置' : `未配置 · 最近状态：${esc(search.secret_status)}`;
  const localSessionControl = state.diagnostics?.local_auth_mode === 'personal_local'
    ? '<p class="muted">个人本机模式：无需配对。</p>'
    : '<button class="text-btn" id="logout-session" type="button">退出本地会话</button>';
  const defaultModel = current
    ? `${current.provider} / ${current.model}`
    : '尚未设置默认模型';
  const modelState = current ? secretLabel(current) : '未配置';
  const appVersion = state.diagnostics?.build_id || state.diagnostics?.app_version || '未知';
  const overview = `<section class="settings-overview"><h3>当前状态</h3><p class="muted">点下面任一项，可以直接进入对应设置。</p><div class="settings-cards"><button type="button" class="settings-card" data-settings-open="models"><span class="settings-card-label">AI 模型</span><strong>${esc(defaultModel)}</strong><span class="settings-card-status">${esc(modelState)}</span></button><button type="button" class="settings-card" data-settings-open="search"><span class="settings-card-label">搜索服务</span><strong>Tavily</strong><span class="settings-card-status">${esc(search.configured ? searchStatus : '尚未配置')}</span></button><button type="button" class="settings-card" data-settings-open="data"><span class="settings-card-label">本机数据</span><strong>当前实例</strong><span class="settings-card-status">Career 数据保存在本机</span></button></div><div class="settings-overview-details"><div class="setting-row"><span>AI 运行模式</span><b>${esc(modeText)}</b></div><div class="setting-row"><span>应用版本</span><span>${esc(appVersion)}</span></div></div></section>`;
  const models = `<section class="settings-section"><div class="pane-heading"><div><h3>模型 Provider</h3><p class="muted">例如 DeepSeek。API Key 只保存在 macOS Keychain；Career 数据库、备份、日志和浏览器响应都不保存完整密钥。</p></div><div class="actions"><button class="primary" id="ai-add">添加模型</button></div></div><section class="ai-config-list">${rows || '<div class="empty">尚未配置 AI 模型。人工资料、简历和求职记录仍可正常使用。</div>'}</section><div class="setting-row"><span>当前模式</span><b>${esc(modeText)}</b></div><div class="setting-row"><span>默认模型</span><span>${current ? esc(`${current.provider} / ${current.model}`) : '尚未设置，AI 操作会提示进入本页配置模型'}</span></div></section>`;
  const searchProvider = `<section class="settings-section"><h3>搜索 Provider · Tavily</h3><p class="muted">这是网页搜索服务，不是模型。只有 Research 经过预览并由你确认后才会搜索。搜索 Key 单独保存在 macOS Keychain。</p><div class="setting-row"><span>配置状态</span><b>${search.configured ? '已配置' : '未配置'}</b></div><div class="setting-row"><span>Secret 状态</span><span>${searchStatus}</span></div><form id="tavily-search-key-form"><label>Tavily API Key<input name="api_key" type="password" autocomplete="new-password" maxlength="10000" required></label><div class="actions"><button class="primary" type="submit">安全保存搜索 Key</button></div><p class="muted">保存只写入并验证 Keychain；不会测试连接或发起搜索。</p></form></section>`;
  const data = `<section class="settings-section"><h3>本机数据与应用</h3><div class="setting-row"><span>数据位置</span><span>Career 本机数据目录</span></div><div class="setting-row"><span>应用版本</span><span>${esc(appVersion)}</span></div><section class="settings-local-use"><h3>本地使用</h3>${localSessionControl}</section><button class="text-btn" data-page="feedback">查看反馈记录 →</button></section>`;
  const panels: Record<SettingsTab, string> = {overview, models, search: searchProvider, data};
  const active = settingsTabs.some(([id]) => id === settingsUI.tab) ? settingsUI.tab : 'overview';
  const tabs = settingsTabs.map(([id, label]) => `<button id="settings-tab-${id}" type="button" role="tab" aria-selected="${active === id}" aria-controls="settings-active-panel" tabindex="${active === id ? 0 : -1}" data-settings-tab="${id}">${label}</button>`).join('');
  return `<section class="settings settings-hub scroll" aria-label="设置"><div class="settings-tabs" role="tablist" aria-label="设置分类">${tabs}</div><div class="settings-panel" id="settings-active-panel" role="tabpanel" aria-labelledby="settings-tab-${active}" tabindex="0">${panels[active]}</div></section>`;
}

export function bindAiSettings(d: Deps) {
  const tabButtons = [...document.querySelectorAll<HTMLButtonElement>('[data-settings-tab]')];
  const activateTab = (tab: SettingsTab) => {
    settingsUI.tab = tab;
    d.render();
    document.querySelector<HTMLButtonElement>(`[data-settings-tab="${tab}"]`)?.focus();
  };
  tabButtons.forEach((button, index) => {
    button.addEventListener('click', () => activateTab(button.dataset.settingsTab as SettingsTab));
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0
        : event.key === 'End' ? tabButtons.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabButtons.length) % tabButtons.length;
      activateTab(tabButtons[next].dataset.settingsTab as SettingsTab);
    });
  });
  document.querySelectorAll<HTMLElement>('[data-settings-open]').forEach(button => {
    button.addEventListener('click', () => activateTab(button.dataset.settingsOpen as SettingsTab));
  });
  const searchForm = document.querySelector<HTMLFormElement>('#tavily-search-key-form');
  searchForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const input = searchForm.elements.namedItem('api_key') as HTMLInputElement;
    const button = searchForm.querySelector<HTMLButtonElement>('button[type=submit]')!;
    const apiKey = input.value;
    button.disabled = true;
    try {
      await d.api('/research/search-provider', {
        api_key: apiKey,
        expected_revision: d.state.search_provider?.revision ?? 0,
      }, 'PUT');
      input.value = '';
      await d.load();
      d.render();
      d.inform('Tavily 搜索 Key 已安全保存；没有测试连接或执行搜索。');
    } catch (e) {
      d.modalError(e);
    } finally {
      input.value = '';
      button.disabled = false;
    }
  });
  const form = (current?: Row) => {
    const editing = Boolean(current);
    const dialog = d.modal(editing ? '编辑模型配置' : '添加模型', `<form id="ai-form"><label>显示名称<input name="display_name" required maxlength="200" value="${esc(current?.display_name)}"></label><label>供应商<input name="provider" required maxlength="100" value="${esc(current?.provider || 'OpenAI-compatible')}"></label><label>Base URL<input name="base_url" required maxlength="2000" type="url" value="${esc(current?.base_url || 'https://api.openai.com/v1')}"></label><label>模型名称<input name="model" required maxlength="500" value="${esc(current?.model)}"></label><p class="muted">DeepSeek 当前模型名称为 <code>deepseek-flash</code>；旧别名会在保存和测试时自动规范化。</p><label>API Key${editing ? '（留空仅保留原 Key；修改供应商或 Base URL 时必须重新录入）' : ''}<input name="api_key" type="password" autocomplete="new-password" maxlength="10000"></label><label><input name="enabled" type="checkbox" ${current?.enabled !== false ? 'checked' : ''}> 启用</label><div class="actions"><button type="button" class="secondary" data-ai-dialog-test>测试连接</button><button type="submit" class="primary">保存</button></div><p class="muted" data-ai-dialog-status></p></form>`);
    const f = dialog.querySelector<HTMLFormElement>('#ai-form')!;
    const values = (): Row => { const raw = Object.fromEntries(new FormData(f).entries()) as Row; return {...raw, enabled: (f.elements.namedItem('enabled') as HTMLInputElement).checked}; };
    const test = async () => { const button = f.querySelector<HTMLButtonElement>('[data-ai-dialog-test]')!; button.disabled = true; try { const raw = values(); const result = await d.api('/ai/test-connection', {provider: raw.provider, base_url: raw.base_url, model: raw.model, api_key: raw.api_key}, 'POST'); (f.querySelector('[data-ai-dialog-status]') as HTMLElement).textContent = result.status === 'success' ? `连接成功（${result.model}）` : `连接失败：${result.code}${result.message ? `（${result.message}）` : ''}`; } catch (e) { (f.querySelector('[data-ai-dialog-status]') as HTMLElement).textContent = e instanceof Error ? e.message : '连接失败'; } finally { button.disabled = false; } };
    dialog.querySelector('[data-ai-dialog-test]')!.addEventListener('click', () => { void test(); });
    f.onsubmit = async event => { event.preventDefault(); const button = f.querySelector<HTMLButtonElement>('[type=submit]')!; button.disabled = true; try { const body: Row = values(); if (editing && current) { body.expected_revision = current.revision; await d.api('/ai/models/' + encodeURIComponent(current.id), body, 'PUT'); } else await d.api('/ai/models', body); dialog.close(); await d.load(); d.render(); d.inform('模型配置已保存。'); } catch (e) { d.modalError(e); } finally { button.disabled = false; } };
  };
  document.querySelector('#ai-add')?.addEventListener('click', () => form());
  document.querySelectorAll<HTMLElement>('[data-ai-edit]').forEach(el => el.onclick = () => form((d.state.ai?.configs || []).find((x:Row) => x.id === el.dataset.aiEdit)));
  document.querySelectorAll<HTMLElement>('[data-ai-test]').forEach(el => el.onclick = async () => { el.setAttribute('aria-busy','true'); try { const result = await d.api('/ai/models/' + encodeURIComponent(el.dataset.aiTest!) + '/test', {}, 'POST'); d.inform(result.status === 'success' ? '连接成功。' : `连接失败：${result.code}`); } catch (e) { d.inform(e instanceof Error ? e.message : '连接失败'); } finally { el.removeAttribute('aria-busy'); } });
  document.querySelectorAll<HTMLElement>('[data-ai-default]').forEach(el => el.onclick = async () => { const config = (d.state.ai?.configs || []).find((x:Row) => x.id === el.dataset.aiDefault); if (!config) return; try { await d.api('/ai/models/' + encodeURIComponent(config.id) + '/default', {expected_revision: config.revision}); await d.load(); d.render(); d.inform('默认模型已切换。'); } catch (e) { d.modalError(e); } });
  document.querySelectorAll<HTMLElement>('[data-ai-delete]').forEach(el => el.onclick = async () => { const id = el.dataset.aiDelete!; const current = id === d.state.ai?.default_model_config_id; if (!window.confirm(current ? '删除当前默认模型后将没有默认 AI 模型。确认删除？' : '删除此模型配置及其 Key？确认删除？')) return; try { await d.api('/ai/models/' + encodeURIComponent(id), {confirm: true}, 'DELETE'); await d.load(); d.render(); d.inform(current ? '已删除模型；当前没有默认 AI 模型。' : '模型配置已删除。'); } catch (e) { d.modalError(e); } });
}
