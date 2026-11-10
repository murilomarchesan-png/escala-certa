import { loadPyodide } from "./runtime/pyodide.mjs";

async function initialize() {
  const runtime = await loadPyodide();
  const files = ["planner.py", "export.py", "browser_api.py"];
  await Promise.all(files.map(async file => {
    const response = await fetch(new URL(file, import.meta.url));
    if (!response.ok) throw new Error("Não foi possível carregar o simulador.");
    runtime.FS.writeFile(file, await response.text());
  }));
  runtime.runPython("from browser_api import handle");
  return runtime.globals.get("handle");
}

let ready;
self.onmessage = async ({data}) => {
  try {
    ready ??= initialize().catch(error => {
      ready = undefined;
      throw error;
    });
    const handle = await ready;
    self.postMessage(JSON.parse(handle(data.path, data.body)));
  } catch {
    self.postMessage({error: "O simulador não carregou. Recarregue a página e tente novamente."});
  }
};
