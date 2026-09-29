import assert from 'node:assert/strict';
import {createServer} from 'vite';
const vite=await createServer({configFile:false,root:new URL('..',import.meta.url).pathname,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true},appType:'custom'});
try {
 const {opportunityHTML}=await vite.ssrLoadModule('/src/opportunity-ui.ts');
 const base={state:{opportunities:[{id:'opportunity:a',company:'虚构公司',title:'岗位',phase:'interview',result:'active'}]},domain:{},journey:{},id:'opportunity:a',filter:'all',anchor:'',communications:[],timeline:{},interviews:[],offer:null};
 assert.match(opportunityHTML({...base,resume:{document_id:'resume:a',document:{}}}),/已保存的工作稿/);
 assert.doesNotMatch(opportunityHTML(base),/还没有简历|已保存的工作稿/);
 assert.match(opportunityHTML({...base,resume:{document:null}}),/尚未创建本机会简历/);
 for(const phase of ['submitted','interview','offer']) {
  const html=opportunityHTML({...base,state:{opportunities:[{...base.state.opportunities[0],phase}]}});
  assert.equal((html.match(/data-add-communication=/g)||[]).length,3,phase);
 }
 const ended=opportunityHTML({...base,state:{opportunities:[{...base.state.opportunities[0],result:'rejected'}]},communications:[{id:'comm:1',content:'保留历史',type:'text'}]});
 assert.doesNotMatch(ended,/data-add-communication=/);
 assert.match(ended,/data-communication="comm:1"/);
 const {loadOpportunityReadback}=await vite.ssrLoadModule('/src/opportunity-scope.ts');
 const calls=[];
 const result=await loadOpportunityReadback('opportunity:a',async path=>{calls.push(path);return {path};});
 assert.ok(calls.includes('/state?view=opportunity&job_id=opportunity%3Aa'));
 assert.ok(calls.includes('/opportunities/opportunity%3Aa/resume'));
 assert.equal(result.resume.path,'/opportunities/opportunity%3Aa/resume');
 assert.equal(result.state.path,'/state?view=opportunity&job_id=opportunity%3Aa');
 console.log('UX-4 opportunity readback PASS');
} finally {await vite.close();}
