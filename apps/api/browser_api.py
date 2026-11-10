import base64
import json

from export import xlsx
from planner import Model, demo


def dispatch(path, body):
    if path == "/v1/demo":
        return demo()
    payload = json.loads(body)
    model = Model(payload["config"])
    if path == "/v1/solve":
        return model.solve()
    report = model.report(payload["assignments"])
    if path == "/v1/validate":
        return report
    if path == "/v1/export":
        return base64.b64encode(xlsx(model, report)).decode("ascii")
    raise ValueError("Ação indisponível.")


def handle(path, body):
    try:
        return json.dumps({"data": dispatch(path, body)})
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        message = str(error) if type(error) is ValueError else "Confira os campos da configuração."
        return json.dumps({"error": message})
