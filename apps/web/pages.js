"use strict";
let plannerWorker;

window.requestPlanner = function (path, payload) {
  return new Promise((resolve, reject) => {
    plannerWorker ??= new Worker(new URL("./worker.mjs", document.baseURI), {type:"module"});
    const worker = plannerWorker;
    worker.onmessage = ({data}) => {
      if (data.error) return reject(new Error(data.error));
      if (path === "/v1/export") {
        const bytes = Uint8Array.from(atob(data.data), char => char.charCodeAt(0));
        return resolve(new Response(bytes, {headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }}));
      }
      resolve(Response.json(data.data));
    };
    worker.onerror = () => {
      worker.terminate();
      plannerWorker = undefined;
      reject(new Error("O simulador não carregou. Recarregue a página e tente novamente."));
    };
    worker.postMessage({path, body: JSON.stringify(payload ?? null)});
  });
};
