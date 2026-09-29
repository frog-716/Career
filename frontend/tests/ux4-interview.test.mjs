import assert from 'node:assert/strict';
import { createServer } from 'vite';
const vite = await createServer({ configFile: false, root: new URL('..', import.meta.url).pathname,
  optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true }, appType: 'custom' });
try {
  const ui = await vite.ssrLoadModule('/src/interview-ui.ts');
  const o = {id:'opportunity:test',phase:'interview',result:'active'};
  const real = {id:'real-one',type:'real',name:'虚构一面',status:'pending'};
  const sim = {id:'sim-one',type:'simulation',name:'虚构模拟',status:'pending',target_real_interview_id:real.id};
  const calls=[];
  const api=async path=>{
    calls.push(path);
    if(path.endsWith('/interviews/real-one'))return real;
    if(path.endsWith('/preparation'))return {focus:'虚构重点',revision:0};
    if(path.endsWith('/raw')||path.endsWith('/final-review'))throw Object.assign(new Error('资料不存在'),{status:404});
    if(path==='/opportunities/opportunity%3Atest/research-patches')return [
      {id:'mine',origin_interview_id:real.id}, {id:'other',origin_interview_id:'real-two'},
    ];
    throw Object.assign(new Error('Not Found'),{status:404});
  };
  assert.equal(typeof ui.loadInterviewDetail,'function','需要通过真实详情读取接口验证路径和轮次隔离');
  const detail=await ui.loadInterviewDetail(o,real.id,api);
  assert.equal(detail.session.id,real.id);
  assert.equal(detail.prep.focus,'虚构重点');
  assert.equal(detail.raw,null);assert.equal(detail.review,null);
  assert.deepEqual(detail.patches.map(p=>p.id),['mine']);
  assert.ok(calls.includes('/opportunities/opportunity%3Atest/research-patches'));
  await assert.rejects(()=>ui.loadInterviewDetail(o,real.id,async path=>{
    if(path.endsWith('/interviews/real-one'))return real;
    throw Object.assign(new Error('读取失败'),{status:500});
  }),/读取失败/,'真实网络/服务错误不能当作无材料吞掉');
  for(const [phase,result] of [['interview','active'],['offer','active'],['offer','accepted'],['interview','withdrawn']]){
    const html=ui.interviewHistoryHTML({...o,phase,result},[real,sim]);
    assert.match(html,/data-interview="real-one"/);
    assert.match(html,/data-interview="sim-one"/);
    assert.doesNotMatch(html,/data-confirm-interview|data-interview-intent="simulation"/,'稳定历史区不推进流程');
  }
  assert.equal(ui.interviewHistoryHTML(o,[]),'');
  console.log('UX-4 interview loading and stable history: PASS');
}finally{await vite.close();}
