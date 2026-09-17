type Obj = Record<string, any>;
type Context = {
  notes: Obj[]; api: (path: string, body?: Obj) => Promise<any>;
  modal: (title: string, content: string, ready?: (d: HTMLDialogElement) => void) => HTMLDialogElement;
  modalError: (error: unknown) => void; load: () => Promise<void>; render: () => void;
  showCandidate: (id: string) => Promise<void>;
};
const e = (v: any) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const types: Obj = {experience:'经历',capability:'能力',project:'项目',achievement:'成果',goal:'职业目标',constraint:'偏好与约束'};
export function bindRecords(ctx: Context) {
  const on = (selector: string, fn: (n: Obj) => void) => document.querySelectorAll<HTMLElement>(selector).forEach(el => el.onclick = () => {
    const id = el.dataset.recordCorrect || el.dataset.recordHistory || el.dataset.recordCandidate;
    const n = ctx.notes.find(n => n.id === id); if (n) fn(n);
  });
  on('[data-record-history]', n => {
    ctx.modal('原始记录与更正历史', '<div data-history>正在读取…</div>', d => {
      void ctx.api(`/journey/notes/${encodeURIComponent(n.id)}/history`).then(result => {
        d.querySelector('[data-history]')!.innerHTML = result.revisions.map((r: Obj) => `<section class="record-history"><h3>${r.revision === 0 ? '原始记录' : `更正视图 v${r.revision}`}</h3><small>${e(r.created_at)}</small><h4>${e(r.title)}</h4><div class="prose">${e(r.content)}</div></section>`).join('');
      }).catch(ctx.modalError);
    });
  });
  on('[data-record-correct]', n => edit(n, false));
  on('[data-record-candidate]', n => edit(n, true));
  function edit(n: Obj, candidate: boolean) {
    ctx.modal(candidate ? '整理为待确认事实' : '更正记录', `<form data-record-form><fieldset><details><summary>查看当前记录 · ${n.note_revision ? `更正视图 v${n.note_revision}` : '原始记录'}</summary><div class="prose">${e(n.content)}</div></details><p class="muted">${candidate ? '只整理允许复用的选段或结论；提交后还需要确认入 Wiki，才会成为分析依据。' : '原始记录和历史更正始终保留。改进后的答案请注明为复盘，勿写成当时的原话。'}</p>${candidate ? `<label>类别<select name="entry_type">${Object.entries(types).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label>` : ''}<label>标题<input name="title" maxlength="500" required value="${e(n.title)}"></label><label>${candidate ? '允许复用的内容' : '更正后的完整内容'}<textarea name="content" required maxlength="100000" placeholder="${candidate ? '仅填写允许复用的选段，补充本人动作、证据及未知项。' : ''}">${candidate ? '' : e(n.content)}</textarea></label>${candidate ? `<label>归属范围<select name="scope"><option value="current">留在当前${n.scope_type === 'job' ? '机会' : '工作卡'}</option><option value="personal">个人 Wiki（可跨任务复用）</option></select></label><label class="wiki-choice"><input type="checkbox" name="promote"><span>允许将所填内容提升为可跨任务复用的个人事实候选</span></label>` : ''}</fieldset><div data-record-conflict></div><button type="submit" class="primary full">${candidate ? '提交待确认' : '保存更正'}</button></form>`, d => {
      const form = d.querySelector<HTMLFormElement>('form')!;
      const fields = form.querySelector('fieldset')!;
      const button = form.querySelector<HTMLButtonElement>('[type=submit]')!;
      let expected = n.note_revision || 0, request: Obj | null = null, saved: Obj | null = null;
      form.onsubmit = async event => {
        event.preventDefault(); if(button.disabled) return;
        if(!saved && !request) {
          const values = new FormData(form), personal = values.get('scope') === 'personal';
          if(personal && values.get('promote') !== 'on') {ctx.modalError(new Error('提升为个人事实需要明确勾选跨任务复用。'));return;}
          request = {expected_revision:expected, title:String(values.get('title')).trim(),content:String(values.get('content')).trim(),idempotency_key:crypto.randomUUID(), ...(candidate ? {entry_type:values.get('entry_type'),scope_type:personal?'personal':n.scope_type,scope_id:personal?'':n.scope_id,promote_to_personal:personal} : {})};
        }
        button.disabled=true;fields.disabled=true;
        try {
          saved ||= await ctx.api(`/journey/notes/${encodeURIComponent(n.id)}/${candidate?'candidate':'correct'}`,request!);
          await ctx.load();d.close();
          if(candidate) await ctx.showCandidate(saved!.id); else ctx.render();
        } catch(error: any) {
          ctx.modalError(error);
          if(saved) button.textContent='保存成功，重试刷新';
          else if(error?.status === 409) {
            request=null;fields.disabled=false;
            const host=d.querySelector<HTMLElement>('[data-record-conflict]')!;
            host.innerHTML='<p>记录已变化，输入已保留。</p><button type="button" data-record-refresh>读取最新记录并比较</button>';
            host.querySelector<HTMLElement>('[data-record-refresh]')!.onclick=async()=>{
              try {
                const history=await ctx.api(`/journey/notes/${encodeURIComponent(n.id)}/history`);
                const latest=history.revisions.at(-1);
                host.innerHTML=`<h3>最新记录 v${e(latest.revision)}</h3><div class="prose">${e(latest.content)}</div><button type="button" data-record-baseline>已核对，以此版本继续</button>`;
                host.querySelector<HTMLElement>('[data-record-baseline]')!.onclick=()=>{expected=latest.revision;host.innerHTML='<p>输入已保留，请检查后再次提交。</p>';};
              }catch(err){ctx.modalError(err);}
            };
          } else if(error?.status && error.status < 500) {request=null;fields.disabled=false;}
          else button.textContent='重试同一请求';
        } finally {button.disabled=false;}
      };
    });
  }
}
