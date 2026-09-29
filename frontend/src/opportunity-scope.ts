/** Read the selected opportunity afresh, including saved draft and frozen materials. */
export async function loadOpportunityReadback(id: string, api: <T = Record<string, any>>(path: string) => Promise<T>) {
 const base='/opportunities/'+encodeURIComponent(id);
 const [state,communications,timeline,interviews,offer,research,resume]=await Promise.all([
  api('/state?view=opportunity&job_id='+encodeURIComponent(id)),
  api<any[]>(base+'/communications'),api(base+'/timeline'),api<any[]>(base+'/interviews'),
  api<Record<string,any>|null>(base+'/offer'),api(base+'/research-overview'),api(base+'/resume'),
 ]);
 return {state,communications,timeline,interviews,offer,research,resume};
}
