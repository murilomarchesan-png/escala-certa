"use strict";
let plannerWorker;
const release = new URL(document.currentScript.src).searchParams.get("v");

function plannerAsset(path) {
  const url = new URL(path, document.baseURI);
  if (release) url.searchParams.set("v", release);
  return url;
}

window.requestPlanner = async function (path, payload) {
  if (path === "/v1/demo") {
    const response = await fetch(plannerAsset("./demo.json"), {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error("O exemplo está indisponível. Tente novamente.");
    return response;
  }
  return new Promise((resolve, reject) => {
    plannerWorker ??= new Worker(plannerAsset("./worker.mjs"), {type:"module"});
    const worker = plannerWorker;
    function reset(message) {
      clearTimeout(timer);
      worker.terminate();
      plannerWorker = undefined;
      reject(new Error(message));
    }
    const timer = setTimeout(() => reset("O cálculo demorou demais. Seu rascunho está preservado. Tente gerar novamente."), 30000);
    worker.onmessage = ({data}) => {
      clearTimeout(timer);
      if (data.error) return reject(new Error(data.error));
      if (path === "/v1/export") {
        const bytes = Uint8Array.from(atob(data.data), char => char.charCodeAt(0));
        return resolve(new Response(bytes, {headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }}));
      }
      resolve(Response.json(data.data));
    };
    worker.onerror = () => reset("O motor não carregou. Verifique a conexão e tente novamente.");
    worker.postMessage({path, body: JSON.stringify(payload ?? null)});
  });
};
