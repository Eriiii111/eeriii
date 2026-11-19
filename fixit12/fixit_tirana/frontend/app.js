const $=id=>document.getElementById(id);
const sessionId=crypto.randomUUID?crypto.randomUUID():String(Date.now());
let reports=[],selectedReport=null,latestAnalysis=null;
async function api(url,options={}){
 const response=await fetch(url,{...options,credentials:"same-origin",headers:{"Content-Type":"application/json",...(options.headers||{})}});
 const data=await response.json().catch(()=>({detail:"Përgjigje e pavlefshme."}));
 if(response.status===401){showLogin();throw new Error(data.detail||"Identifikohu përsëri.");}
 if(!response.ok)throw new Error(data.detail||"Ndodhi një gabim.");
 return data;
}
function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function showLogin(){ $("appView").classList.add("hidden");$("loginView").classList.remove("hidden");}
function showApp(user){$("loginView").classList.add("hidden");$("appView").classList.remove("hidden");$("adminName").textContent=user||"admin";$("settingsUser").textContent=user||"admin";loadAll();}
$("loginForm").addEventListener("submit",async e=>{
 e.preventDefault();$("loginError").textContent="";
 try{const d=await api("/api/auth/login",{method:"POST",body:JSON.stringify({username:$("username").value,password:$("password").value})});$("password").value="";showApp(d.username);}
 catch(err){$("loginError").textContent=err.message;}
});
$("logoutBtn").onclick=async()=>{try{await api("/api/auth/logout",{method:"POST"});}finally{showLogin();}};
async function init(){try{const d=await api("/api/auth/me");showApp(d.username);}catch{showLogin();}}
function go(page){
 document.querySelectorAll(".page").forEach(x=>x.classList.remove("active"));
 $("page-"+page).classList.add("active");
 document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===page));
 const names={overview:"Përmbledhje",reports:"Raportet",assistant:"Asistenti AI",settings:"Cilësimet"};
 $("pageCrumb").textContent=names[page];$("sidebar").classList.remove("open");
 if(page==="assistant")refreshGemini();
}
document.querySelectorAll(".nav-item").forEach(b=>b.onclick=()=>go(b.dataset.page));
document.querySelectorAll("[data-goto]").forEach(b=>b.onclick=()=>go(b.dataset.goto));
$("menuToggle").onclick=()=>$("sidebar").classList.toggle("open");
function statusClass(s){return "status-"+s.replaceAll(" ","-");}
function statusPill(s){return `<span class="status-pill ${statusClass(s)}">${esc(s)}</span>`;}
async function loadAll(){await Promise.all([loadReports(),loadDashboard(),refreshGemini()]);}
async function loadReports(){
 reports=await api("/api/reports");$("navReportCount").textContent=reports.length;
 renderReports();$("assistantReport").innerHTML='<option value="">Zgjidh raportin…</option>'+reports.map(r=>`<option value="${r.id}">#${r.id} · ${esc(r.title)}</option>`).join("");
}
function renderReports(){
 const q=($("searchReports")?.value||"").toLowerCase(),st=$("filterStatus")?.value||"",cat=$("filterCategory")?.value||"";
 const rows=reports.filter(r=>(!q||(r.title+" "+r.address).toLowerCase().includes(q))&&(!st||r.status===st)&&(!cat||r.category===cat));
 $("reportRows").innerHTML=rows.length?rows.map(r=>`<tr><td><div class="table-title"><span class="table-id">#${r.id}</span><b>${esc(r.title)}</b></div></td><td>${esc(r.category)}</td><td>${esc(r.address||"—")}</td><td>${esc(r.created_at||"")}</td><td>${statusPill(r.status)}</td><td><button class="table-actions" onclick="showDetail(${r.id})">Detaje ↗</button></td></tr>`).join(""):'<tr><td colspan="6" class="empty-state">Nuk u gjet asnjë raport.</td></tr>';
 const recent=reports.slice(0,5);
 $("recentReports").innerHTML=recent.length?recent.map(r=>`<div class="recent-row"><div class="recent-symbol">▤</div><div class="recent-info"><b>${esc(r.title)}</b><small>#${r.id} · ${esc(r.address||"Pa adresë")}</small></div>${statusPill(r.status)}</div>`).join(""):'<div class="empty-state">Ende nuk ka raporte të regjistruara.</div>';
}
async function loadDashboard(){
 const d=await api("/api/dashboard");$("statTotal").textContent=d.total;$("statNew").textContent=d.new;$("statProgress").textContent=d.in_progress;$("statResolved").textContent=d.resolved;
 const cats=d.categories||[],max=Math.max(1,...cats.map(x=>x.n));
 $("categoryChart").innerHTML=cats.length?cats.map(c=>`<div class="category-item"><div class="category-label"><span>${esc(c.category)}</span><b>${c.n}</b></div><div class="bar-track"><div class="bar-fill" style="width:${c.n/max*100}%"></div></div></div>`).join(""):'<div class="empty-state">Nuk ka ende të dhëna.</div>';
}
$("searchReports").oninput=renderReports;$("filterStatus").onchange=renderReports;$("filterCategory").onchange=renderReports;
function openReportModal(){$("reportModal").classList.remove("hidden");$("formError").textContent="";}
$("newReportBtn").onclick=openReportModal;$("newReportBtn2").onclick=openReportModal;
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>$(b.dataset.close==="modal"?"reportModal":"detailModal").classList.add("hidden"));
$("reportForm").onsubmit=async e=>{
 e.preventDefault();$("formError").textContent="";
 try{await api("/api/reports",{method:"POST",body:JSON.stringify({title:$("title").value,description:$("description").value,address:$("address").value,category:$("category").value})});
 e.target.reset();$("reportModal").classList.add("hidden");await loadReports();await loadDashboard();}
 catch(err){$("formError").textContent=err.message;}
};
window.showDetail=async id=>{
 const r=await api(`/api/reports/${id}`);selectedReport=id;
 $("detailTitle").textContent=`#${r.id} · ${r.title}`;
 $("detailBody").innerHTML=`<div class="detail-line"><b>Përshkrimi</b>${esc(r.description)}</div><div class="detail-line"><b>Adresa</b>${esc(r.address||"Nuk është dhënë")}</div><div class="detail-line"><b>Kategoria</b>${esc(r.category)}</div><div class="detail-line"><b>Data e regjistrimit</b>${esc(r.created_at)}</div><div class="detail-status"><label>Ndrysho statusin</label><select id="detailStatus"><option ${r.status==="I ri"?"selected":""}>I ri</option><option ${r.status==="Në proces"?"selected":""}>Në proces</option><option ${r.status==="Zgjidhur"?"selected":""}>Zgjidhur</option><option ${r.status==="Refuzuar"?"selected":""}>Refuzuar</option></select><button class="btn btn-primary" onclick="updateStatus(${r.id})">Ruaj statusin</button> <button class="btn btn-outline" onclick="useReport(${r.id})">Analizo me AI</button></div>`;
 $("detailModal").classList.remove("hidden");
};
window.updateStatus=async id=>{try{await api(`/api/reports/${id}/status`,{method:"PATCH",body:JSON.stringify({status:$("detailStatus").value})});$("detailModal").classList.add("hidden");await loadReports();await loadDashboard();}catch(e){alert(e.message);}};
window.useReport=id=>{$("detailModal").classList.add("hidden");$("assistantReport").value=id;go("assistant");runAnalysis();};
async function refreshGemini(){
 try{const d=await api("/api/ai/health");const label=d.available?`Gemini aktiv · ${d.model}`:"Gemini joaktiv";
 $("geminiStatus").innerHTML=`<i style="background:${d.available?"#27ad78":"#d98a28"}"></i>${esc(label)}`;$("settingsGemini").textContent=d.available?"Aktiv":"Joaktiv";$("settingsModel").textContent=d.model||"—";
 }catch(e){$("geminiStatus").textContent="Nuk u verifikua";$("settingsGemini").textContent="Nuk u verifikua";}
}
$("recheckGemini").onclick=refreshGemini;
function bubble(text,role){const d=document.createElement("div");d.className=`chat-bubble ${role}`;d.textContent=text;$("chatMessages").appendChild(d);$("chatMessages").scrollTop=$("chatMessages").scrollHeight;return d;}
document.querySelectorAll(".suggestion-chips button").forEach(b=>b.onclick=()=>{$("chatInput").value=b.textContent;$("chatForm").requestSubmit();});
$("chatForm").onsubmit=async e=>{
 e.preventDefault();const message=$("chatInput").value.trim();if(!message)return;
 $("chatMessages").querySelector(".chat-welcome")?.remove();bubble(message,"user");$("chatInput").value="";
 const pending=bubble("Gemini po përgatit përgjigjen…","assistant");
 try{const d=await api("/api/ai/chat",{method:"POST",body:JSON.stringify({message,session_id:sessionId,report_id:$("assistantReport").value?Number($("assistantReport").value):null})});pending.textContent=d.answer;}
 catch(err){pending.textContent=err.message;pending.style.color="#b34b4b";}
};
$("clearChat").onclick=async()=>{
 try{await api(`/api/ai/chat/${sessionId}`,{method:"DELETE"});$("chatMessages").innerHTML='<div class="chat-welcome"><div class="ai-orb">✳</div><h3>Bisedë e re</h3><p>Si mund të të ndihmoj?</p></div>';}
 catch(e){alert(e.message);}
};
async function runAnalysis(){
 const id=Number($("assistantReport").value);if(!id){$("analysisOutput").textContent="Zgjidh fillimisht një raport.";return;}
 $("analysisOutput").textContent="Gemini po analizon raportin…";
 try{const d=await api("/api/ai/analyze-report",{method:"POST",body:JSON.stringify({report_id:id})});latestAnalysis=d;
 $("analysisOutput").innerHTML=`<h4>Analiza</h4>${esc(d.problem_analysis)}<h4>Kategoria</h4>${esc(d.category)}<h4>Institucioni</h4>${esc(d.responsible_institution)}<h4>Prioriteti: ${esc(d.priority)}</h4>${esc(d.priority_reason||"")}<h4>Rekomandimet</h4><ul>${d.recommendations.map((x,i)=>`<li>${esc(x)} <button class="text-btn" onclick="saveRec(${id},${i})">Ruaj</button></li>`).join("")}</ul><h4>Hapat</h4><ul>${d.suggested_steps.map(x=>`<li>${esc(x)}</li>`).join("")}</ul><h4>Shënime</h4>${esc(d.additional_notes)}`;
 }catch(e){$("analysisOutput").textContent=e.message;}
}
$("runAnalysis").onclick=runAnalysis;
window.saveRec=async(id,i)=>{try{await api(`/api/reports/${id}/recommendations`,{method:"POST",body:JSON.stringify({recommendation:latestAnalysis.recommendations[i]})});alert("Rekomandimi u ruajt.");}catch(e){alert(e.message);}};
init();
