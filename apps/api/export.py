from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def xlsx(model, report):
    rows = [
        ["Escala Certa | Simulação", model.data["unit"]],
        ["Revisão jurídica pendente", report["ruleset"], "Hipótese semanal", model.data["phase"]],
        ["Horas de cobertura mínima faltantes", report["deficit"] / 4],
        ["Pessoa", "Equipe", "Data inicial", "Turno", "Início", "Fim", "Pausa início", "Pausa fim", "Função"],
    ]
    for p, d, s, role in report["assignments"]:
        person, shift = model.people[p], model.data["shifts"][s]
        end = shift["end"] + (" (+1 dia)" if model.shifts[s][1] >= 96 else "")
        rows.append([person["name"], person["team"], (model.start + timedelta(days=d)).isoformat(),
                     shift["name"], shift["start"], end, shift["pause_start"], shift["pause_end"], role])
    rows.append(["Alertas"])
    rows.extend([f["person"], f["message"], f["clause"], f["source"] or ""] for f in report["findings"])
    rows.append(["Cobertura por intervalo", "Função", "Mínimo", "Desejado", "Escalado", "Falta"])
    for t, role, low, want, actual, missing in report["coverage"]:
        day, quarter = divmod(t, 96)
        stamp = (model.start + timedelta(days=day)).isoformat()
        rows.append([f"{stamp} {quarter//4:02}:{quarter%4*15:02}", role, low, want, actual, missing])
    xml_rows = []
    for number, row in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row):
            ref = chr(65 + column) + str(number)
            if isinstance(value, (float, int)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as file:
        file.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        file.writestr("_rels/.rels", f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        file.writestr("xl/workbook.xml", f'<workbook xmlns="{MAIN}" xmlns:r="{OFFICE}"><sheets><sheet name="Simulação" sheetId="1" r:id="rId1"/></sheets></workbook>')
        file.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        file.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{MAIN}"><cols><col min="1" max="9" width="23" customWidth="1"/></cols><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
    return buffer.getvalue()


