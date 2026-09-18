/** Canonical Opportunity workspace. Lifecycle values come only from domain DTOs. */
import { bindInterviews, interviewStageHTML } from './interview-ui';
import { bindOffer, offerStageHTML } from './offer-ui';
type Row = Record<string, any>;
type Context = {state: Row; domain: Row; journey: Row; id: string; filter: string; anchor: string; communications:Row[]; timeline:Row; interviews:Row[]; offer:Row|null; research?:Row};
type Actions = {api: (path:string, body?:Row, method?:string)=>Promise<any>; refresh:()=>Promise<void>; go:(id:string,filter?:string)=>void};
const phases: Record<string,string> = {resume:'写简历',submitted:'已投递',interview:'面试',offer:'Offer'};
const results: Record<string,string> = {active:'推进中',accepted:'已接受',rejected:'被招聘方终止',withdrawn:'主动退出'};
const views = [['all','全部'],...Object.entries(phases),['ended','已结束']];
const escape = (value:unknown) => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const canonical = (id:string) => id.startsWith('opportunity:') ? id : 'opportunity:'+id;
function link(url:string) {return /^https?:\/\//.test(url||'') ? `<a class="op-external" href="${escape(url)}" target="_blank" rel="noopener noreferrer" aria-label="打开招聘链接">招聘链接 ↗</a>` : '';}
function versionLabel(ctx:Context,v:Row) { const o=(ctx.state.opportunities||[]).find((o:Row)=>o.id===v.opportunity_id); if(v.version_kind==='submission')return v.name; return (o?o.company+' · '+o.title:'历史材料')+' · '+v.name; }
function selected(ctx:Context) {return (ctx.state.opportunities||[]).find((o:Row)=>o.id===canonical(ctx.id));}
function localDay(){const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function displayDay(value:unknown,fallback='日期待核对'){if(!value)return fallback;const date=new Date(String(value));if(Number.isNaN(date.valueOf()))return fallback;const parts=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);const pick=(type:string)=>parts.find(p=>p.type===type)?.value||'';return `${pick('year')}-${pick('month')}-${pick('day')}`;}
function communicationLabel(type:unknown){return ({text:'线上沟通',phone:'电话沟通',other:'其他沟通'} as Row)[String(type)]||'历史沟通 · 类型待核对';}

export function opportunityHTML(ctx:Context) {
 const items:Row[]=ctx.state.opportunities||[];
 if (!ctx.id) {
  const filtered=items.filter(o=>ctx.filter==='all'||(!o.read_only&&(ctx.filter==='ended'?o.result!=='active':o.result==='active'&&o.phase===ctx.filter)));
  const rows=filtered.map(o=>`<tr data-opportunity="${escape(o.id)}" tabindex="0" role="link" aria-label="打开${escape(o.company)} ${escape(o.title)}"><td>${escape(o.company)}</td><td><strong>${escape(o.title)}</strong>${o.read_only?'<small>历史资料 · 状态待核对</small>':''}</td><td><span class="op-badge">${escape(phases[o.phase]||'待核对')}</span>${!o.read_only&&o.result!=='active'?`<small>${escape(results[o.result])}</small>`:''}</td><td>${escape(o.phase_changed_on||'历史日期待核对')}</td><td>${link(o.action_url)}</td></tr>`).join('');
  return `<section class="op-page"><div class="op-heading"><div><p class="op-eyebrow">一次尝试，一条机会</p><h2>机会管线</h2></div><button class="primary" id="op-create">添加机会</button></div><nav class="op-views" aria-label="机会视图">${views.map(([key,label])=>`<button data-op-view="${key}" aria-pressed="${ctx.filter===key}" class="${ctx.filter===key?'selected':''}">${label}</button>`).join('')}</nav>${filtered.length?`<div class="op-table-wrap"><table class="op-table"><thead><tr><th>公司</th><th>岗位</th><th>阶段</th><th>阶段日期</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="op-empty"><h3>这里还没有机会</h3><p>添加公司、岗位和 JD，即可开始。简历不是前置条件。</p></div>'}<p class="muted op-caption">${filtered.length} 条 · 历史待核对资料不会自动计入四阶段或已结束。</p></section>`;
 }
 const o=selected(ctx);
 if (!o)return '<section class="op-page"><button class="text-btn" id="op-back">← 返回机会管线</button><div class="op-empty"><h2>机会不存在</h2><p>链接无法对应到已有机会，未切换到其他记录。</p></div></section>';
 const alias=o.legacy_job_id||o.id.slice('opportunity:'.length);
 const applications:Row[]=(ctx.state.applications||[]).filter((a:Row)=>a.opportunity_id===o.id||a.job_id===alias);
 const resumeDocument=(ctx.state.resume_documents||[]).find((d:Row)=>d.opportunity_id===o.id);
 const typedNoteIds=new Set([...(ctx.communications||[]).map((x:Row)=>x.raw_note_id),ctx.offer?.raw_note_id].filter(Boolean));
 const notes:Row[]=(ctx.journey.notes||[]).filter((n:Row)=>n.scope_type==='job'&&n.scope_id===alias&&!typedNoteIds.has(n.id));
 const ordered=ctx.anchor ? [...notes.filter(n=>n.kind===ctx.anchor),...notes.filter(n=>n.kind!==ctx.anchor)] : notes;
 const material=applications.map(a=>`<article class="op-record"><h4>${a.submission_format===3?'投递材料':'历史投递'} · ${escape(displayDay(a.submitted_on||a.applied_at))}</h4>${a.resume_snapshot?`<details><summary>查看冻结简历</summary><pre>${escape(a.resume_snapshot?.content||JSON.stringify(a.resume_snapshot?.document||{},null,2))}</pre></details>`:'<p>本次未使用简历</p>'}<p>打招呼语：${escape(a.submitted_greeting_snapshot?.state==='captured'?a.submitted_greeting_snapshot.content:a.submitted_greeting_snapshot?.state==='not_used'?'本次未使用':'历史未记录')}</p>${a.artifact_id?`<a href="/api/artifacts/${encodeURIComponent(a.artifact_id)}?download=true" target="_blank" rel="noopener">下载原 PDF</a>`:''}</article>`).join('');
 const resumeActions=o.read_only||o.result!=='active'||o.phase!=='resume'?'':`<div class="op-next-action"><p><strong>${resumeDocument?'继续准备本机会的简历':'还没有为这个机会准备简历'}</strong><br><span>简历可选，不使用简历也可以记录投递。</span></p><div class="actions"><button id="op-resume" class="secondary">编辑简历</button><button id="op-greeting" class="secondary">编辑打招呼语</button>${!applications.length?'<button id="op-submit" class="primary">记录已投递</button>':''}</div></div><details class="op-current-greeting"><summary>当前打招呼语</summary><p class="prose">${escape(o.greeting??'还没有准备打招呼语')}</p><small>修改当前内容不会改变已有投递快照。</small></details>`;
 const recent=(ctx.communications||[])[0];
 const communicationActions=o.phase==='submitted'&&o.result==='active'?`<div class="op-communication-actions"><button class="primary" data-add-communication="text">添加线上沟通</button><button class="secondary" data-add-communication="phone">记录电话沟通</button><button class="secondary" data-add-communication="other">添加其他沟通</button></div>${recent?`<button class="op-recent" data-communication="${escape(recent.id)}"><span>最近沟通 · ${escape(recent.occurred_on||'日期待核对')}</span><strong>${escape(communicationLabel(recent.type))}</strong><small>${escape(recent.content)}</small></button>`:'<p class="muted">投递后还没有记录招聘沟通。</p>'}`:'';
 const timelineItems=[...(ctx.timeline?.items||[]),...(ctx.timeline?.unknown_date_items||[])];
 const timeline=timelineItems.map((item:Row)=>`<li class="op-timeline-item"><time>${escape(item.occurred_on||'日期待核对')}</time><div><strong>${escape(item.title)}</strong><p>${escape(item.summary)}</p>${item.target?.kind==='communication'?`<button class="text-btn" data-communication="${escape(item.object_id)}">查看沟通</button>`:item.target?.kind==='submission'?`<button class="text-btn" data-submission="${escape(item.object_id)}">查看投递材料</button>`:item.target?.kind==='interview'?`<button class="text-btn" data-interview="${escape(item.object_id)}">查看 Interview</button>`:item.target?.kind==='offer'?'<button class="text-btn" data-offer-anchor>查看 Offer</button>':''}</div></li>`).join('');

 const placeholders:Record<string,string>={resume:'准备本机会的简历与打招呼语，也可以不使用简历直接记录投递。',submitted:'记录现实中已经发生的招聘沟通；只有明确动作才推进阶段。',interview:'围绕当前或下一轮真实面试完成准备、模拟、面试记录与复盘。',offer:'当前处于 Offer 阶段。条件变化由你明确更新，谈薪沟通不会自动改写。'};
 const interviewArea=interviewStageHTML(o,ctx.interviews||[]);
 const offerArea=offerStageHTML(o,ctx.offer);
 const currentWork=o.result!=='active'?offerArea:o.phase==='resume'?resumeActions:o.phase==='submitted'?communicationActions+interviewArea+offerArea:o.phase==='interview'?interviewArea+offerArea:offerArea;
 const legacySection=ordered.length?`<section class="op-section"><details><summary>历史资料（需要时查看）</summary><p class="muted">原始记录保留可读；只有需要人工核对时才会进入当前业务。</p>${ordered.map(n=>`<details class="op-record" ${n.kind===ctx.anchor?'open':''}><summary>${escape(n.title||'历史记录')} · ${escape(n.created_at)}</summary><div class="prose">${escape(n.content)}</div><a href="/#footprint?record=${encodeURIComponent(n.id)}">查看来源</a></details>`).join('')}</details></section>`:'';
 const research=ctx.research||{company:{items:[]},opportunity:{items:[]}};
 const researchItems=(research.company?.items||[]).concat(research.opportunity?.items||[]);
 const researchHTML=researchItems.length?researchItems.map((item:Row)=>`<article class="op-research-item"><span class="op-badge">${escape(item.classification||'unknown')}</span><strong>${escape(item.category)}</strong><p>${escape(item.content)}</p>${(item.source_refs||[]).map((ref:Row)=>ref.url?`<a href="${escape(ref.url)}" target="_blank" rel="noopener noreferrer">${escape(ref.title||ref.url)} ↗</a>`:'').join('')}</article>`).join(''):'<p class="muted">尚无已确认岗位情报。可更新研究，或手动添加。</p>';
 return `<section class="op-page"><button class="text-btn" id="op-back">← 返回机会管线</button><header class="op-workspace-heading"><div><p class="op-eyebrow">${escape(o.company)}</p><h2>${escape(o.title)}</h2><div class="op-meta"><span class="op-badge">${escape(phases[o.phase]||'历史待核对')}</span><span>${escape(o.phase_changed_on||'历史日期待核对')}</span>${!o.read_only?`<span>${escape(results[o.result])}</span>`:''}${link(o.action_url)}</div></div>${!o.read_only?`<div class="actions"><button class="secondary" id="op-edit">编辑机会</button>${o.result==='active'&&o.phase!=='offer'?'<button class="text-btn" id="op-end">结束机会</button>':''}</div>`:''}</header><ol class="op-phase-strip" aria-label="当前阶段">${Object.entries(phases).map(([key,label])=>`<li ${o.phase===key?'aria-current="step" class="current"':''}>${label}</li>`).join('')}</ol><section class="op-stage"><div class="op-stage-title"><div><p class="op-eyebrow">现在该做什么</p><h3>${o.read_only?'核对这条历史机会':o.result!=='active'?'回看这次已结束的机会':o.phase==='submitted'?'记录招聘沟通':o.phase==='interview'?'准备当前 / 下一轮面试':o.phase==='offer'?'核对 Offer 并决定下一步':'准备投递'}</h3></div></div><p>${escape(o.read_only?'原始记录保留可读。只有确实需要时才进行人工核对。':o.result!=='active'?`${results[o.result]} · ${displayDay(o.result_changed_at,'结束日期待核对')}。投递材料和历史活动仍可查看。`:placeholders[o.phase])}</p>${currentWork}</section><section class="op-section"><div class="op-section-heading"><h3>岗位情报</h3><div class="actions"><button class="secondary" id="op-update-research" ${o.read_only?'disabled':''}>更新研究</button><button class="quiet" id="op-edit-research" ${o.read_only?'disabled':''}>手动编辑</button></div></div><div class="prose"><strong>当前 JD</strong><p>${escape(o.jd)}</p></div><div class="op-research-list">${researchHTML}</div></section><section class="op-section" id="op-materials"><h3>投递材料</h3>${material||'<p class="muted">还没有已登记的投递材料。</p>'}</section><section class="op-section"><h3>Timeline</h3><p class="muted">由已发生的投递、沟通、面试、Offer 和结果聚合。</p>${timeline?`<ol class="op-timeline">${timeline}</ol>`:'<p class="muted">还没有可显示的进展。</p>'}</section>${legacySection}</section>`;
}

export function bindOpportunity(ctx:Context,actions:Actions) {
 const selectedOpportunity=selected(ctx);
 const interviewActions=selectedOpportunity?bindInterviews(selectedOpportunity,ctx.interviews||[],actions):null;
 if(selectedOpportunity)bindOffer(selectedOpportunity,ctx.offer,actions);
 document.querySelectorAll<HTMLElement>('[data-op-view]').forEach(el=>el.onclick=()=>actions.go('',el.dataset.opView));
 document.querySelectorAll<HTMLElement>('[data-opportunity]').forEach(el=>{
  el.onclick=(event)=>{if(!(event.target as HTMLElement).closest('a'))actions.go(el.dataset.opportunity!);};
  el.onkeydown=(event)=>{if(event.key==='Enter'&&event.target===el)actions.go(el.dataset.opportunity!);};
 });
 document.querySelector('#op-back')?.addEventListener('click',()=>actions.go(''));
 document.querySelector('#op-create')?.addEventListener('click',()=>form());
 document.querySelector('#op-edit')?.addEventListener('click',()=>form(selected(ctx)));
 document.querySelector('#op-end')?.addEventListener('click',()=>end(selected(ctx)));
 document.querySelectorAll<HTMLElement>('[data-end-opportunity]').forEach(el=>el.onclick=()=>end(selected(ctx),el.dataset.endOpportunity));
 document.querySelector('#op-resume')?.addEventListener('click',()=>resumeStart(selected(ctx)));
 document.querySelector('#op-greeting')?.addEventListener('click',()=>greeting(selected(ctx)));
 document.querySelector('#op-submit')?.addEventListener('click',()=>submitted(selected(ctx)));
 document.querySelector('#op-update-research')?.addEventListener('click',()=>updateResearch(selected(ctx)));
 document.querySelector('#op-edit-research')?.addEventListener('click',()=>editResearch(selected(ctx)));
 document.querySelectorAll<HTMLElement>('[data-add-communication]').forEach(el=>el.onclick=()=>communicationForm(selected(ctx),el.dataset.addCommunication!));
 document.querySelectorAll<HTMLElement>('[data-communication]').forEach(el=>el.onclick=()=>void communicationDetail(selected(ctx),el.dataset.communication!));
 document.querySelectorAll<HTMLElement>('[data-submission]').forEach(el=>el.onclick=()=>document.querySelector('#op-materials')?.scrollIntoView({behavior:'smooth'}));
 document.querySelectorAll<HTMLElement>('[data-offer-anchor]').forEach(el=>el.onclick=()=>document.querySelector('#op-offer')?.scrollIntoView({behavior:'smooth'}));
 function dialog(title:string,body:string) {
  const d=document.createElement('dialog');d.className='op-dialog';
  d.innerHTML=`<div class="op-heading"><h2>${title}</h2><button type="button" data-close>关闭</button></div><div class="op-error" role="alert" hidden></div>${body}`;
  document.body.append(d);d.querySelector('[data-close]')!.addEventListener('click',()=>d.close());
  d.addEventListener('input',()=>d.dataset.dirty='true');d.addEventListener('close',()=>d.remove());d.showModal();return d;
 }
 function failure(d:HTMLDialogElement,error:unknown) {const alert=d.querySelector<HTMLElement>('.op-error')!;alert.hidden=false;alert.textContent=(error as any).status>=500?'尚未确认操作结果。请保留当前选择并用原请求重试。':String((error as Error).message);}
 async function communicationDetail(o:Row,id:string) {
 try {const event=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/communications/'+encodeURIComponent(id));
   const controls=o.read_only?'<p class="notice">该历史机会尚未核对，只读保留；不能更正或删除。</p>':`<div class="actions"><button class="primary" data-edit>编辑</button><button class="secondary" data-delete>删除</button>${o.phase==='submitted'&&o.result==='active'?'<button class="primary" data-confirm-from-communication>确认真实面试</button>':''}</div>`;
   const d=dialog(communicationLabel(event.type),`<p class="op-eyebrow">${escape(event.occurred_on||'日期待核对')}</p>${event.legacy?'<p class="notice">历史记录的类型可能待核对；编辑时由你明确确认。</p>':''}<div class="prose op-communication-content">${escape(event.content||'原文缺失')}</div>${controls}`);
   d.querySelector<HTMLElement>('[data-edit]')?.addEventListener('click',()=>{d.close();communicationForm(o,event.type||'other',event);});
   d.querySelector<HTMLElement>('[data-confirm-from-communication]')?.addEventListener('click',()=>{d.close();interviewActions?.confirmFromCommunication(event.id);});
   d.querySelector<HTMLElement>('[data-delete]')?.addEventListener('click',()=>{if(!window.confirm('删除后将从沟通列表和时间线隐藏。确认删除？'))return;void (async()=>{try{await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/communications/'+encodeURIComponent(event.id)+'/delete',{expected_revision:event.revision,idempotency_key:crypto.randomUUID()});d.close();await actions.refresh();actions.go(o.id);}catch(error){failure(d,error);}})();});
  } catch(error){const d=dialog('沟通不可用','<p>该沟通已删除或不属于当前机会。</p>');failure(d,error);}
 }
 function communicationForm(o:Row,type:string,current?:Row) {
  const d=dialog(current?'更正沟通':communicationLabel(type),`<form><p>只记录已经发生的沟通，不会改变机会阶段或创建面试。</p>${current?`<label>类型<select name="type"><option value="text">线上沟通</option><option value="phone">电话沟通</option><option value="other">其他沟通</option></select></label>`:''}<label>日期<input name="occurred_on" type="date" required value="${escape(current?.occurred_on||localDay())}"></label><label>内容<textarea name="content" rows="8" maxlength="100000" required>${escape(current?.content||'')}</textarea></label><button class="primary" type="submit">${current?'保存更正':'记录沟通'}</button></form>`);
  const f=d.querySelector('form')!;if(current)(f.elements.namedItem('type') as HTMLSelectElement).value=current.type||'other';let revision=current?.revision;let pending:Row|undefined;let signature='';
  f.onsubmit=async event=>{event.preventDefault();const button=f.querySelector<HTMLButtonElement>('button[type=submit]')!;button.disabled=true;
   const fields=Object.fromEntries(new FormData(f).entries()) as Row;fields.type=current?fields.type:type;const body:Row={...fields,...(current?{expected_revision:revision}:{})};const next=JSON.stringify(body);if(!pending||next!==signature){signature=next;pending={...body,idempotency_key:crypto.randomUUID()};}
   try{await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/communications'+(current?'/'+encodeURIComponent(current.id):''),pending,current?'PUT':'POST');d.close();await actions.refresh();actions.go(o.id);}
   catch(error){failure(d,error);if(current&&(error as any).status===409){const latest=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/communications/'+encodeURIComponent(current.id));d.querySelector('[data-compare]')?.remove();const compare=document.createElement('div');compare.dataset.compare='true';compare.innerHTML=`<p>服务器当前内容：${escape(latest.content)}</p><button type="button">已核对差异，保留我的输入继续</button>`;f.append(compare);compare.querySelector('button')!.onclick=()=>{revision=latest.revision;pending=undefined;compare.remove();};}}
   finally{button.disabled=false;}
  };
 }
 async function updateResearch(o:Row) {
  const d=dialog('更新岗位情报','<p>系统会搜索当前公司和岗位，生成带来源的 proposal；确认前不会改写 Research。</p><button class="primary" type="button" data-run>开始 Web Research</button><div class="op-research-proposal" hidden></div>');
  d.querySelector('[data-run]')!.addEventListener('click',async()=>{const b=d.querySelector<HTMLButtonElement>('[data-run]')!;b.disabled=true;try{const p=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/research/update',{idempotency_key:crypto.randomUUID()});const box=d.querySelector<HTMLElement>('.op-research-proposal')!;box.hidden=false;box.innerHTML='<h3>待确认变化</h3>'+[...(p.company_items||[]),...(p.opportunity_items||[])].map((x:Row)=>`<article><strong>${escape(x.category)}</strong><p>${escape(x.content)}</p>${(x.source_refs||[]).map((r:Row)=>`<a href="${escape(r.url||'#')}" target="_blank" rel="noopener">${escape(r.title||r.url||'来源')} ↗</a>`).join('')}</article>`).join('')+'<div class="actions"><button class="primary" data-accept>接受</button><button class="secondary" data-reject>拒绝</button></div>';const resolve=async(decision:string)=>{try{await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/research-proposals/'+encodeURIComponent(p.id)+'/resolve',{decision});d.close();await actions.refresh();actions.go(o.id);}catch(error){failure(d,error);}};box.querySelector('[data-accept]')!.addEventListener('click',()=>void resolve('accept'));box.querySelector('[data-reject]')!.addEventListener('click',()=>void resolve('reject'));}catch(error){failure(d,error);}finally{b.disabled=false;}});
 }
 function editResearch(o:Row) {
  const d=dialog('手动编辑岗位情报',`<form><label>分类<input name="category" required value="unknown"></label><label>类型<select name="classification"><option value="fact">事实</option><option value="inference">推断</option><option value="unknown">Unknown</option></select></label><label>内容<textarea name="content" required rows="7"></textarea></label><button class="primary" type="submit">保存到当前 Research</button></form>`);const f=d.querySelector('form')!;f.onsubmit=async e=>{e.preventDefault();const fields=Object.fromEntries(new FormData(f).entries());try{await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/research/items',{...fields,scope:'opportunity',expected_revision:ctx.research?.opportunity?.revision||0,idempotency_key:crypto.randomUUID(),source_refs:[]});d.close();await actions.refresh();actions.go(o.id);}catch(error){failure(d,error);}};
 }
 async function resumeStart(o:Row) {
  const current=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/resume');
  if(current.document_id){location.href='/editor.html?document_id='+encodeURIComponent(current.document_id);return;}
  const versions=(await actions.api('/editor/versions')).versions;
  const legacy=await actions.api('/editor');
  const d=dialog('开始制作本机会简历',`<form><p>${escape(o.company)} · ${escape(o.title)}</p><label>复制来源<select name="source"><option value="blank">空白创建</option>${legacy.revision?'<option value="legacy_draft">明确复制历史 editor-main</option>':''}${versions.map((v:Row)=>`<option value="${escape(v.id)}">复制版本：${escape(versionLabel(ctx,v))}</option>`).join('')}</select></label><p>只复制内容，来源版本和用途保持不变。</p><button class="primary" type="submit">创建独立工作稿</button></form>`);
  const f=d.querySelector('form')!;let pending:Row|undefined;let signature='';
  f.onsubmit=async e=>{e.preventDefault();const button=f.querySelector<HTMLButtonElement>('button')!;button.disabled=true;
   try {const choice=String(new FormData(f).get('source'));let source:Row={kind:choice};
    if(choice==='legacy_draft')source={kind:choice,source_revision:legacy.revision,source_hash:legacy.document_hash};
    else if(choice!=='blank'){const v=await actions.api('/editor/versions/'+encodeURIComponent(choice));source={kind:'version',source_version_id:v.id,source_document_hash:v.document_hash};}
    const next=JSON.stringify(source);if(!pending||signature!==next){signature=next;pending={expected_opportunity_revision:o.revision,idempotency_key:crypto.randomUUID(),source};}
    const result=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/resume/start',pending);d.close();location.href='/editor.html?document_id='+encodeURIComponent(result.document_id);
   }catch(error){failure(d,error);}finally{button.disabled=false;}};
 }
 function greeting(o:Row) {
  const d=dialog('编辑当前打招呼语',`<form><p>当前表达可继续修改，历史投递快照永久保留。</p><label>当前内容<textarea name="content" rows="7" maxlength="20000">${escape(o.greeting??'')}</textarea></label><button class="primary" type="submit">保存当前内容</button></form>`);
  const f=d.querySelector('form')!;let rev=o.revision;let pending:Row|undefined;
  f.onsubmit=async e=>{e.preventDefault();const b=f.querySelector<HTMLButtonElement>('button')!;b.disabled=true;
   const content=String(new FormData(f).get('content'));if(!pending||pending.content!==content||pending.expected_revision!==rev)pending={content,expected_revision:rev,idempotency_key:crypto.randomUUID()};
   try{await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/greeting',pending);d.close();await actions.refresh();actions.go(o.id);}
   catch(error){failure(d,error);if((error as any).status===409){const current=await actions.api('/opportunities/'+encodeURIComponent(o.id));const compare=document.createElement('div');compare.innerHTML=`<p>服务器当前内容：${escape(current.greeting??'尚未准备')}</p><button type="button">已核对差异，保留我的输入继续</button>`;f.append(compare);compare.querySelector('button')!.onclick=()=>{rev=current.revision;pending=undefined;compare.remove();};}}
   finally{b.disabled=false;}};
 }
 async function submitted(o:Row) {
  const draft=await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/resume');
  const versions=((await actions.api('/editor/versions')).versions as Row[]).filter(v=>v.opportunity_id===o.id);
  const d=dialog('记录现实中已完成的投递',`<form><p>${escape(o.company)} · ${escape(o.title)}</p><label>实际使用的简历<select name="resume">${draft.document_id?'<option value="draft">当前工作稿（前往纸面确认）</option>':''}<option value="none">本次不使用简历</option>${versions.map((v:Row)=>`<option value="${escape(v.id)}">明确使用版本：${escape(versionLabel(ctx,v))}</option>`).join('')}</select></label><p data-greeting>本次打招呼语：${escape(o.greeting??'本次未使用打招呼语')}</p><p>仅登记已发生的投递，不替你向外发送。日期自动记录。</p><button class="primary" type="submit">确认记录已投递</button></form>`);
  const f=d.querySelector('form')!;let pending:Row|undefined;let choiceKey='';let revision=o.revision;
  f.onsubmit=async e=>{e.preventDefault();const b=f.querySelector<HTMLButtonElement>('button')!;b.disabled=true;
   try {const choice=String(new FormData(f).get('resume'));
    if(choice==='draft'){d.close();location.href='/editor.html?document_id='+encodeURIComponent(draft.document_id)+'&submit=1';return;}
    if(!pending||choice!==choiceKey){let resume:Row={mode:'none'};
     if(choice!=='none'){const v=await actions.api('/editor/versions/'+encodeURIComponent(choice));resume={mode:'version',source_version_id:v.id,source_document_hash:v.document_hash,source_artifact_hash:v.artifact_hash};}
     pending={expected_revision:revision,idempotency_key:crypto.randomUUID(),resume};choiceKey=choice;
    }
    await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/submitted',pending);d.close();await actions.refresh();actions.go(o.id);
   }catch(error){failure(d,error);if((error as any).status===409){
    const latest=await actions.api('/opportunities/'+encodeURIComponent(o.id));
    d.querySelector('[data-compare]')?.remove();const box=document.createElement('div');box.dataset.compare='true';
    box.innerHTML=`<p>服务器当前阶段：${escape(phases[latest.phase])}；当前打招呼语：${escape(latest.greeting??'本次未使用')}</p><button type="button">核对最新状态并继续</button>`;f.append(box);
    box.querySelector('button')!.onclick=async()=>{if(latest.phase!=='resume'||latest.result!=='active'){d.close();await actions.refresh();actions.go(o.id);return;}
     revision=latest.revision;pending=undefined;d.querySelector('[data-greeting]')!.textContent='本次打招呼语：'+(latest.greeting??'本次未使用打招呼语');box.remove();};
   }}finally{b.disabled=false;}};
 }
 function form(o?:Row) {
  const companies=(ctx.domain.objects||[]).filter((x:Row)=>x.kind==='company');
  const d=dialog(o?'编辑机会':'添加机会',`<form><label>公司<input name="company_name" required maxlength="500" value="${escape(o?.company||'')}"></label><label>或选择已有公司<select name="company_id"><option value="">按输入名称匹配</option>${companies.map((c:Row)=>`<option value="${escape(c.id)}">${escape(c.name)}${c.description?' · '+escape(c.description):''}</option>`).join('')}</select></label><label>岗位<input name="title" required maxlength="500" value="${escape(o?.title||'')}"></label><label>JD<textarea name="jd" required rows="7">${escape(o?.jd||'')}</textarea></label><label>招聘链接（可选）<input name="action_url" type="url" value="${escape(o?.action_url||'')}"></label><div class="op-comparison" hidden></div><button class="primary" type="submit">保存机会</button></form>`);
  const f=d.querySelector('form')!;const selector=f.elements.namedItem('company_id') as HTMLSelectElement;
  if(o)selector.value=o.company_id;
  selector.onchange=()=>{const input=f.elements.namedItem('company_name') as HTMLInputElement;input.required=!selector.value;};
  if(o)(f.elements.namedItem('company_name') as HTMLInputElement).required=false;
  f.querySelector('[name=company_name]')!.addEventListener('input',()=>{selector.value='';(f.elements.namedItem('company_name') as HTMLInputElement).required=true;});
  let revision=o?.revision;let pending:{signature:string;body:Row}|undefined;
  f.onsubmit=async event=>{
   event.preventDefault();const button=f.querySelector<HTMLButtonElement>('[type=submit]')!;if(button.disabled)return;
   const fields=Object.fromEntries(new FormData(f).entries());
   if(fields.company_id)delete fields.company_name;else delete fields.company_id;
   const base:Row={...fields,...(o?{expected_revision:revision}:{})};const signature=JSON.stringify(base);
   if(!pending||pending.signature!==signature)pending={signature,body:{...base,idempotency_key:crypto.randomUUID()}};
   button.disabled=true;
   try {const result=await actions.api('/opportunities'+(o?'/'+encodeURIComponent(o.id):''),pending.body);d.close();await actions.refresh();actions.go(result.id);}
   catch(error) {
    const alert=d.querySelector<HTMLElement>('.op-error')!;alert.hidden=false;alert.textContent=String((error as Error).message);
    if(o&&(error as any).status===409) {
     const latest=await actions.api('/opportunities/'+encodeURIComponent(o.id));const box=d.querySelector<HTMLElement>('.op-comparison')!;box.hidden=false;
     box.innerHTML=`<h3>服务器当前内容</h3><p>${escape(latest.company)} · ${escape(latest.title)}</p><pre>${escape(latest.jd)}</pre><button type="button">载入最新版本，保留我的输入</button>`;
     box.querySelector('button')!.onclick=()=>{revision=latest.revision;pending=undefined;box.querySelector('button')!.remove();alert.textContent='已载入最新版本号。请核对差异后再次保存；你的输入保留。';};
    }
   } finally {button.disabled=false;}
  };
 }
 function end(o:Row,preset?:string) {
  const options=[['rejected','被招聘方终止'],['withdrawn','主动退出']];
  const chosen=options.find(([value])=>value===preset);
  const d=dialog(chosen?chosen[1]:'结束机会',`<p>保留最后阶段及历史材料，不会创建任职记录。</p><form>${chosen?`<input type="hidden" name="result" value="${chosen[0]}"><p>确认将这次机会记为“${chosen[1]}”？</p>`:`<label>结束结果<select name="result">${options.map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></label>`}<button class="primary" type="submit">确认${chosen?chosen[1]:'结束'}</button></form>`);
  const f=d.querySelector('form')!;const key=crypto.randomUUID();
  f.onsubmit=async event=>{
   event.preventDefault();const button=f.querySelector<HTMLButtonElement>('button')!;button.disabled=true;
   try {const result=String(new FormData(f).get('result'));await actions.api('/opportunities/'+encodeURIComponent(o.id)+'/end',{result,expected_revision:o.revision,idempotency_key:key,...(result==='accepted'?{offer_id:o.confirmed_offer_id}:{})});d.close();await actions.refresh();actions.go(o.id,'ended');}
   catch(error){const alert=d.querySelector<HTMLElement>('.op-error')!;alert.hidden=false;alert.textContent=(error as Error).message;button.disabled=false;}
  };
 }
}
