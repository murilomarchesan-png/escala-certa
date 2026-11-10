"use strict";
const $ = id => document.getElementById(id);
const steps = ["Restaurante", "Pessoas", "Cobertura", "Preferências", "Resultado"];
const roles = ["Cozinha", "Atendimento", "Caixa", "Limpeza"];
const state = { step: 0, config: null, solution: null, scenario: 0, busy: false, team: "", week: 0, example: false, draft: null };
const draftKey = "escala-certa-workspace-v1";
const weekdays = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const safe = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const input = (label, attrs) => `<label>${label}<input ${attrs}></label>`;
const option = (value, text, current) => `<option value="${safe(value)}" ${String(current) === String(value) ? "selected" : ""}>${safe(text)}</option>`;
const select = (label, attrs, options) => `<label>${label}<select ${attrs}>${options.join("")}</select></label>`;
const field = (label, key, value, type = "text", extra = "") => input(label, `data-field="${key}" type="${type}" value="${safe(value)}" ${extra}`);
const control = key => `data-field="${key}"`;
const shiftOptions = (c, current) => c.shifts.map((shift, i) => option(i, shift.name, current));
const dayLabel = (c, day, weekday = false) => {
  const d = new Date(c.start + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + day);
  return new Intl.DateTimeFormat("pt-BR", {timeZone:"UTC",day:"2-digit",month:"2-digit", ...(weekday ? {weekday:"short"} : {})}).format(d);
};
const time = quarter => `${String(Math.floor(quarter / 4)).padStart(2,"0")}:${String(quarter % 4 * 15).padStart(2,"0")}`;

function save() {
  if (!state.config || state.example) return;
  state.draft = {config: state.config, solution: state.solution, scenario: state.scenario, step: state.step};
  try {
    localStorage.setItem(draftKey, JSON.stringify(state.draft));
  } catch {
    $("status").textContent = "O navegador não conseguiu guardar o rascunho. Exporte o resultado antes de fechar.";
  }
}
function changeConfig() {
  state.solution = null;
  save();
}
async function request(path, payload) {
  if (window.requestPlanner) return window.requestPlanner(path, payload);
  const options = payload === undefined ? {} : {
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
  };
  const response = await fetch(path, options);
  if (!response.ok) throw new Error((await response.json()).error);
  return response;
}
async function run(task, waiting) {
  state.busy = true;
  render();
  $("status").textContent = waiting;
  try {
    await task();
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message;
  } finally {
    state.busy = false;
    render();
  }
}
function start() {
  const today = new Date();
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() + (8 - today.getDay()) % 7);
  const date = [monday.getFullYear(), monday.getMonth()+1, monday.getDate()].map(n=>String(n).padStart(2,"0")).join("-");
  const draft = state.draft;
  Object.assign(state, {example:false, week:0, team:"", scenario:draft?.scenario ?? 0, solution:draft?.solution ?? null,
    config:draft?.config ?? {unit:"", start:date, days:7, phase:44, people:[], shifts:[
      {name:"Turno 1",start:"08:00",end:"12:00",pause_start:"",pause_end:""}
    ], demand:[]}});
  go(draft?.step ?? 0);
}
function loadExample() {
  return run(async () => {
    state.config = await (await request("/v1/demo")).json();
    state.example = true;
    state.step = 0;
    state.week = 0;
    state.team = "";
    changeConfig();
  }, "Abrindo exemplo…");
}
async function calculate() {
  if (!state.config.unit.trim()) throw new Error("Preencha o nome da unidade na etapa Restaurante.");
  if (!state.config.people.length) throw new Error("Cadastre pelo menos uma pessoa na etapa Pessoas.");
  if (!state.config.demand.some(r=>r.minimum>0 && (r.weekdays === undefined || r.weekdays.length))) {
    throw new Error("Defina pelo menos uma faixa com cobertura mínima na etapa Cobertura.");
  }
  state.solution = await (await request("/v1/solve", {config:state.config})).json();
  state.scenario = 0;
  state.week = 0;
  save();
}
function restaurant(c) {
  return `<p class="muted">Informe a unidade, o período e os turnos. Os horários seguem São Paulo.</p>
  <div class="fields" data-group="root">
  ${field("Nome da unidade","unit",c.unit)}
  ${field("Início do ciclo","start",c.start,"date")}
  ${select("Duração",control("days"),[7,14,21,28].map(n => option(n,n+" dias",c.days)))}</div>
  <h3>Turnos disponíveis</h3><p class="muted">Use quartos de hora. O fim anterior ao início indica virada de dia.</p>
  ${c.shifts.map((s,i) => `<div class="record" data-group="shifts" data-index="${i}">
    <div class="fields">${field("Nome do turno","name",s.name)}
    ${field("Início","start",s.start,"time",'step="900"')}
    ${field("Fim","end",s.end,"time",'step="900"')}
    ${field("Pausa começa","pause_start",s.pause_start,"time",'step="900"')}
    ${field("Pausa termina","pause_end",s.pause_end,"time",'step="900"')}</div>
    <button data-action="remove-shift" data-index="${i}">Remover turno</button></div>`).join("")}
  <button data-action="add-shift">Adicionar turno</button>`;
}
function people(c) {
  return `<p class="muted">Use nome curto ou identificação interna. Equipe é opcional. Informe os dias indisponíveis sem registrar o motivo.</p>
  ${c.people.map((p,i) => `<details data-group="people" data-index="${i}">
    <summary>${safe(p.name)} · ${safe(p.skills.join(", "))}${p.team ? " · Equipe "+safe(p.team) : ""}</summary>
    <div class="fields">${field("Nome curto ou identificador","name",p.name)}
    ${field("Equipe","team",p.team)}
    ${field("Limite semanal contratual","hours",p.hours,"number",'min="1" max="44"')}
    ${select("Regime",control("regime"),[option("integral","CLT integral",p.regime),option("especial","Regime especial — em revisão",p.regime)])}
    ${select("Turno fixo",control("fixed"),[option("","Flexível",p.fixed ?? ""),...shiftOptions(c,p.fixed)])}
    ${field("Dias indisponíveis (1 a "+c.days+", separados por vírgula)","blocked",p.blocked.map(d => d+1).join(","))}
    </div><div class="checks" role="group" aria-label="Funções habilitadas">
    ${roles.map(r => `<label><input type="checkbox" data-field="skills" value="${r}" ${p.skills.includes(r)?"checked":""}>${r}</label>`).join("")}</div>
    <button data-action="remove-person" data-index="${i}">Remover pessoa</button>
  </details>`).join("")}<button data-action="add-person">Adicionar pessoa</button>`;
}
function coverage(c) {
  return `<p class="muted">O mínimo define a falta operacional. O desejado serve para comparar alternativas. Faixas sobrepostas da mesma função usam a maior exigência.</p>
  ${c.demand.map((r,i) => `<div class="record" data-group="demand" data-index="${i}"><div class="fields">
    ${select("Faixa do turno",control("shift"),shiftOptions(c,r.shift))}
    ${select("Função",control("role"),roles.map(name => option(name,name,r.role)))}
    ${field("Mínimo","minimum",r.minimum,"number",'min="0" max="100"')}
    ${field("Desejado","target",r.target,"number",'min="0" max="100"')}
    </div><div class="checks" role="group" aria-label="Dias de cobertura">
    ${weekdays.map((day,d)=>`<label><input type="checkbox" data-field="weekdays" value="${d}" ${(r.weekdays ?? [0,1,2,3,4,5,6]).includes(d)?"checked":""}>${day}</label>`).join("")}
    </div><button data-action="remove-demand" data-index="${i}">Remover faixa</button></div>`).join("")}
  <button data-action="add-demand">Adicionar faixa</button>`;
}
function preferences(c) {
  return `<p class="muted">As fases são hipóteses. O simulador aplica o limite selecionado ao ciclo inteiro, com até 8h diárias de trabalho ordinário.</p>
  <div class="fields" data-group="root">${select("Hipótese de jornada semanal",control("phase"),
    [44,42,40].map(n => option(n,n+"h · simulação",c.phase)))}</div>
  <h3>Preferência de folga por pessoa</h3><div class="fields">
  ${c.people.map((p,i) => `<div data-group="people" data-index="${i}">${select(safe(p.name),control("rest"),
    [["juntas","Seguidas"],["separadas","Separadas"],["","Indiferente"]].map(([k,v]) => option(k,v,p.rest)))}</div>`).join("")}
  </div>`;
}
function result(c) {
  if (!state.solution) return '<p>Gere opções para revisar o calendário e o mapa de cobertura.</p><button data-action="solve" class="primary">Gerar escala</button>';
  const solution = state.solution;
  const report = solution.scenarios[state.scenario];
  const percent = report.minimum ? ((1-report.deficit/report.minimum)*100).toLocaleString("pt-BR",{maximumFractionDigits:1})+"%" : "Sem demanda";
  const teamList = [...new Set(c.people.map(p => p.team).filter(Boolean))];
  const days = Array.from({length:7}, (_, i) => state.week*7+i);
  const currentAssignments = new Map();
  for (const [index, a] of report.assignments.entries()) {
    const key = a[0]+","+a[1];
    if (!currentAssignments.has(key)) currentAssignments.set(key,[]);
    currentAssignments.get(key).push([index,a]);
  }
  const rows = report.coverage.filter(r => Math.floor(r[0]/96) >= days[0] &&
    (Math.floor(r[0]/96) <= days[6] || (state.week === c.days/7-1 && Math.floor(r[0]/96) === c.days)));
  return `<p>${safe(c.unit)} · ${dayLabel(c,0)} a ${dayLabel(c,c.days-1)} · hipótese de ${c.phase}h · ${safe(report.ruleset)}</p>
    <div class="actions no-print"><button data-action="solve" class="primary">Gerar novamente</button>
    <button data-action="export">Baixar Excel</button><button data-action="print">Imprimir / Salvar PDF</button></div>
    <div class="fields no-print">
    ${select("Cenário",'id="scenario"',solution.scenarios.map((s,i) => option(i,`Opção ${i+1} · ${s.deficit/4} h mínimas em falta`,state.scenario)))}
    ${select("Semana",'id="week"',Array.from({length:c.days/7},(_,i)=>option(i,dayLabel(c,i*7)+" a "+dayLabel(c,i*7+6),state.week)))}
    ${select("Equipe",'id="team"',[option("","Todas",state.team),...teamList.map(t=>option(t,t,state.team))])}</div>
    <div class="metrics">
      <div class="metric"><strong>${percent}</strong>Cobertura mínima</div>
      <div class="metric"><strong>${report.deficit/4} h</strong>Falta para o mínimo</div>
      <div class="metric"><strong>${report.desired/4} h</strong>Falta para o desejado</div>
      <div class="metric"><strong>${report.findings.length}</strong>Conflitos na simulação</div>
    </div>
    ${report.deficit ? `<p class="alert">${solution.structural ? "O catálogo atual comprova pelo menos "+solution.structural/4+" h de falta por ausência de pessoas elegíveis nos intervalos." : "A busca encontrou lacunas. Ainda pode haver uma combinação melhor."} Consulte os intervalos abaixo e ajuste os turnos ou disponibilize reforço habilitado.</p>` : ""}
    ${report.unsupported.length ? `<p>Fora da geração por regime em revisão · ${safe(report.unsupported.join(", "))}</p>` : ""}
    <details class="no-print"><summary>Comparar alternativas</summary><div class="scroller" tabindex="0" aria-label="Comparação de alternativas">
    <table><thead><tr><th>Opção</th><th>Horas mínimas em falta</th><th>Horas desejadas em falta</th><th>Alocações</th><th>Conflitos</th></tr></thead>
    <tbody>${solution.scenarios.map((s,i)=>`<tr><th scope="row">Opção ${i+1}</th><td>${s.deficit/4}</td><td>${s.desired/4}</td><td>${s.assignments.length}</td><td>${s.findings.length}</td></tr>`).join("")}</tbody></table></div></details>
    <h3>Calendário semanal</h3><p class="muted no-print">Remova uma alocação no calendário ou use a edição manual. A cobertura é recalculada após cada mudança.</p>
    <div class="scroller" tabindex="0" aria-label="Calendário com rolagem"><table class="calendar"><thead><tr><th>Pessoa</th>
    ${days.map(d=>`<th>${dayLabel(c,d,true)}</th>`).join("")}</tr></thead><tbody>
    ${c.people.map((p,i)=> !state.team || state.team === p.team ? `<tr><th scope="row">${safe(p.name)}</th>${days.map(d=>`<td>${(currentAssignments.get(i+","+d) || []).map(([k,a]) =>
      `<div><b>${safe(c.shifts[a[2]].name)}</b><br>${safe(c.shifts[a[2]].start)}–${safe(c.shifts[a[2]].end)}<br>${a[3]}<br><button data-action="unassign" data-index="${k}" aria-label="Remover turno de ${safe(p.name)} em ${dayLabel(c,d)}">Remover</button></div>`).join("") || "Livre"}</td>`).join("")}</tr>` : "").join("")}
    </tbody></table></div>
    <details class="no-print"><summary>Adicionar alocação manual</summary><div class="fields">
      ${select("Pessoa",'id="person"',c.people.map((p,i)=>option(i,p.name,0)))}
      ${select("Dia",'id="day"',days.map(d=>option(d,dayLabel(c,d,true),days[0])))}
      ${select("Turno",'id="shift"',shiftOptions(c,0))}
      ${select("Função",'id="role"',roles.map(r=>option(r,r,roles[0])))}
    </div><button data-action="assign">Adicionar e validar</button></details>
    ${report.findings.length ? `<h3>Conflitos</h3><ul>${report.findings.map(f=>`<li>${safe(f.person)} · ${safe(f.message)} · ${f.source ? `<a href="${safe(f.source)}">${safe(f.clause)}</a>` : safe(f.clause)}</li>`).join("")}</ul>` : ""}
    <h3>Cobertura por 15 minutos</h3><div class="scroller" tabindex="0" aria-label="Cobertura com rolagem"><table>
    <thead><tr><th>Dia e hora</th><th>Função</th><th>Mínimo</th><th>Desejado</th><th>Escalado</th><th>Falta</th></tr></thead><tbody>
    ${rows.map(([t,r,m,w,a,g])=>`<tr class="${g?"gap":"full"}"><td>${dayLabel(c,Math.floor(t/96))} · ${time(t%96)}</td><td>${r}</td><td>${m}</td><td>${w}</td><td>${a}</td><td>${g || "Coberto"}</td></tr>`).join("")}</tbody></table></div>
    <p class="muted">Referências · <a href="https://www2.camara.leg.br/legin/fed/emecon/2026/emendaconstitucional-141-16-outubro-2026-800062-publicacaooriginal-181622-pl.html">EC 141/2026</a> · <a href="https://sinthoresp.com.br/site/convencoes-coletivas/">Instrumentos coletivos do SINTHORESP</a></p>`;
}
function render() {
  $("steps").innerHTML = steps.map((s,i)=>`<button data-step="${i}" ${state.step===i?'aria-current="step"':""}>${i+1}. ${s}</button>`).join("");
  const c = state.config;
  $("start").textContent = state.example && state.draft ? "Voltar à minha escala" : !c && state.draft ? "Retomar minha escala" : "Montar minha escala";
  $("panel").innerHTML = `<h2 id="panel-title" tabindex="-1">${steps[state.step]}</h2>` +
    (state.example ? '<p class="muted">Exemplo fictício. Seu rascunho fica separado.</p>' : "") +
    (c ? [restaurant,people,coverage,preferences,result][state.step](c) : "<p>Comece pelo cadastro da sua unidade.</p>");
  $("navigation").hidden = !c;
  $("back").disabled = state.busy || state.step===0;
  $("next").disabled = state.busy || state.step===4;
  $("next").textContent = state.step===3 ? "Gerar escala" : "Continuar";
  for (const control of document.querySelectorAll("#demo,#start,#steps button,#panel button,#panel input,#panel select")) {
    control.disabled = state.busy || (control.closest("#steps") && !c);
  }
}
function go(step) {
  state.step = step;
  save();
  render();
  $("panel-title").focus();
}
function onChange(event) {
  const target = event.target;
  const id = target.id;
  if (["scenario","week","team"].includes(id)) {
    state[id] = id==="team" ? target.value : Number(target.value);
    save();
    render();
    $(id).focus();
    return;
  }
  const key = target.dataset.field;
  if (!key) return;
  const {group,index} = target.closest("[data-group]").dataset;
  const object = group==="root" ? state.config : state.config[group][Number(index)];
  let value = target.value;
  if (["phase","days","shift","hours","minimum","target"].includes(key)) value = Number(value);
  if (key==="fixed") value = value==="" ? null : Number(value);
  if (key==="skills") value = [...target.closest(".checks").querySelectorAll("input:checked")].map(c=>c.value);
  if (key==="weekdays") value = [...target.closest(".checks").querySelectorAll("input:checked")].map(c=>Number(c.value));
  if (key==="blocked") {
    const days = value.split(",").map(s=>s.trim()).filter(Boolean).map(Number);
    if (days.some(d=>!Number.isInteger(d)||d<1||d>state.config.days)) {
      $("status").textContent = "Use números de dias dentro do ciclo.";
      target.value = object.blocked.map(d=>d+1).join(",");
      return;
    }
    value = days.map(d=>d-1);
  }
  object[key] = value;
  $("status").textContent = "";
  changeConfig();
  const summary = target.closest("details")?.querySelector("summary");
  if (summary && group === "people") summary.textContent = [object.name,object.skills.join(", "),object.team && "Equipe "+object.team].filter(Boolean).join(" · ");
}
async function edit(assignments) {
  const response = await request("/v1/validate",{config:state.config,assignments});
  state.solution.scenarios[state.scenario] = await response.json();
  save();
}
function onAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button || state.busy) return;
  const action = button.dataset.action;
  const index = Number(button.dataset.index);
  const c = state.config;
  if (action==="solve") return run(calculate,"Calculando alternativas…");
  if (action==="print") return window.print();
  if (["assign","unassign","export"].includes(action)) {
    const assignments = [...state.solution.scenarios[state.scenario].assignments];
    if (action==="assign") assignments.push([Number($("person").value),Number($("day").value),Number($("shift").value),$("role").value]);
    if (action==="unassign") assignments.splice(index,1);
    if (action!=="export") return run(()=>edit(assignments),"Recalculando cobertura…");
    return run(async () => {
      const response = await request("/v1/export",{config:c,assignments});
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href=url;
      anchor.download="escala-certa-simulacao.xlsx";
      anchor.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    },"Preparando Excel…");
  }
  if (action==="add-shift") c.shifts.push({name:"Novo turno",start:"08:00",end:"12:00",pause_start:"",pause_end:""});
  if (action==="remove-shift" && c.shifts.length>1) {
    c.shifts.splice(index,1);
    c.demand = c.demand.filter(r=>r.shift!==index).map(r=>({...r,shift:r.shift>index?r.shift-1:r.shift}));
    c.people.forEach(p=>{if(p.fixed===index)p.fixed=null;else if(p.fixed>index)p.fixed--;});
  }
  if (action==="add-person") c.people.push({name:"",skills:[roles[0]],team:"",blocked:[],fixed:null,rest:"",regime:"integral",hours:40});
  if (action==="remove-person") c.people.splice(index,1);
  if (action==="add-demand") c.demand.push({shift:0,role:roles[0],minimum:1,target:1});
  if (action==="remove-demand") c.demand.splice(index,1);
  changeConfig();
  render();
  if (action==="add-person") {
    const details = $("panel").querySelector("details:last-of-type");
    details.open = true;
    details.querySelector("input").focus();
  }
}
$("start").onclick = () => start();
$("demo").onclick = () => loadExample();
$("back").onclick = () => go(state.step-1);
$("next").onclick = () => {
  if (state.step<3) return go(state.step+1);
  go(4);
  if (!state.solution) run(calculate,"Calculando alternativas…");
};
$("steps").onclick = event => {
  if (event.target.dataset.step !== undefined) go(Number(event.target.dataset.step));
};
$("panel").addEventListener("change",onChange);
$("panel").addEventListener("click",onAction);
try { state.draft = JSON.parse(localStorage.getItem(draftKey)); } catch {}
render();
