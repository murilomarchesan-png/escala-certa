"""Excel export shared by the local server and the browser worker."""
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
import re
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZIP_DEFLATED

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
BODY, TITLE, HEADER, STRIPE, FREE, ALERT, DAY, SECTION = range(8)
EPOCH = date(1899, 12, 30)
ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def xml_text(value):
    return escape(ILLEGAL_XML.sub("", str(value)))


def unique_tab(name, used):
    name = re.sub(r"[:\\/?*\[\]]", " ", ILLEGAL_XML.sub("", name))
    base = (" ".join(name.split()).strip("'") or "Funcionário")[:31].rstrip("'")
    result, index = base, 2
    while result.casefold() in used:
        suffix = f" ({index})"
        result = base[:31-len(suffix)].rstrip("'") + suffix
        index += 1
    used.add(result.casefold())
    return result


def time_text(quarter):
    hour, minute = divmod(quarter, 4)
    return f"{hour % 24:02}:{minute * 15:02}"


def schedule_rows(model, report):
    assignments = defaultdict(list)
    continuation = set()
    for p, d, s, role in sorted(report["assignments"], key=lambda a: (a[0], a[1], model.shifts[a[2]][0], a[3])):
        shift = model.data["shifts"][s]
        _, end, work = model.shifts[s]
        overnight = end > 96
        ends_next_day = end >= 96
        if overnight:
            continuation.add((p, d + 1))
        interval = f'{shift["start"]}–{shift["end"]}' + (" (+1 dia)" if ends_next_day else "")
        pause = f'{shift["pause_start"]}–{shift["pause_end"]}' if shift["pause_start"] else ""
        assignments[p, d].append((shift["name"], interval, role, pause, len(work) / 4))
    return assignments, continuation


def manager_sheet(model, report, assignments, continuation):
    period = f"{model.start:%d/%m/%Y} a {model.start + timedelta(days=model.days-1):%d/%m/%Y}"
    coverage = (1 - report["deficit"] / report["minimum"]) * 100 if report["minimum"] else None
    rows = [
        (["Escala gerencial · " + model.data["unit"]], TITLE, 30),
        ([period + " · Revisão jurídica pendente"], ALERT, 24),
        (["Pessoas", len(model.people), "Cobertura mínima", f"{coverage:.1f}%" if coverage is not None else "Sem demanda",
          "Falta mínima (h)", report["deficit"] / 4, "Falta desejada (h)", report["desired"] / 4,
          "Conflitos", len(report["findings"])], SECTION, 30),
        ([f'Hipótese semanal de {model.data["phase"]}h · {report["ruleset"]} · Consulte Cobertura para ver os intervalos por função.'], BODY, 28),
    ]
    merged = ["A1:L1", "A2:L2", "A4:L4"]
    for week in range(0, model.days, 7):
        days = list(range(week, week+7))
        stamps = [model.start + timedelta(days=d) for d in days]
        rows.append(([f"Semana {week//7+1} · {stamps[0]:%d/%m} a {stamps[-1]:%d/%m}"], SECTION, 24))
        merged.append(f"A{len(rows)}:L{len(rows)}")
        rows.append((["Pessoa", "Funções", "Equipe", "Turno-base", *[f"{WEEKDAYS[d.weekday()]} {d:%d/%m}" for d in stamps],
                      "Horas alocadas"], HEADER, 27))
        for p, person in enumerate(model.people):
            fixed = person["fixed"]
            base = "Flexível"
            if fixed is not None:
                shift = model.data["shifts"][fixed]
                base = f'{shift["name"]}\n{shift["start"]}–{shift["end"]}'
            cells, hours, height = [], 0, 46
            for d in days:
                jobs = assignments[p, d]
                lines = [f"{interval}\n{role} · {name}" + (f"\nPausa {pause}" if pause else "")
                         for name, interval, role, pause, _ in jobs]
                if (p, d) in continuation:
                    lines.insert(0, "Continuação do dia anterior")
                hours += sum(job[-1] for job in jobs)
                height = min(240, max(height, sum(1 + line.count("\n") for line in lines) * 24))
                cells.append("\n".join(lines) if lines else ("Indisponível" if d in person["blocked"] else "Sem turno"))
            rows.append(([person["name"], ", ".join(person["skills"]) or "—", person["team"] or "—", base,
                          *cells, hours], STRIPE if p % 2 else BODY, height))
    if report["findings"] or report["unsupported"]:
        rows.append((["Conflitos e pendências"], ALERT, 24))
        merged.append(f"A{len(rows)}:L{len(rows)}")
        for finding in report["findings"]:
            rows.append(([f'{finding["person"]} · {finding["message"]} · {finding["clause"]} {finding["source"] or ""}'], BODY, 36))
            merged.append(f"A{len(rows)}:L{len(rows)}")
        if report["unsupported"]:
            rows.append((["Regime em revisão · " + ", ".join(report["unsupported"])], ALERT, 40))
            merged.append(f"A{len(rows)}:L{len(rows)}")
    return rows, [23, 19, 13, 20, *([24]*7), 15], merged, (1, 6)


def employee_sheet(model, p, assignments, continuation):
    person = model.people[p]
    period = f"{model.start:%d/%m/%Y} a {model.start + timedelta(days=model.days-1):%d/%m/%Y}"
    total = sum(job[-1] for d in range(model.days) for job in assignments[p, d])
    rows = [
        (["Escala individual · " + person["name"]], TITLE, 30),
        ([f'{model.data["unit"]} · {period} · Revisão jurídica pendente'], ALERT, 26),
        (["Equipe", person["team"] or "—", "Horas alocadas", total], SECTION, 25),
        (["Data", "Dia", "Turno / situação", "Horário", "Função", "Pausa", "Horas"], HEADER, 25),
    ]
    for d in range(model.days + 1):
        stamp = model.start + timedelta(days=d)
        jobs = assignments[p, d]
        continued = (p, d) in continuation
        if d == model.days and not continued:
            break
        if continued:
            rows.append(([(stamp-EPOCH).days, WEEKDAYS[stamp.weekday()], "Continuação do dia anterior"], FREE, 27))
        for name, interval, role, pause, hours in jobs:
            rows.append(([(stamp-EPOCH).days, WEEKDAYS[stamp.weekday()], name, interval, role, pause or "—", hours],
                         STRIPE if d % 2 else BODY, 24))
        if not jobs and not continued:
            label = "Indisponível" if d in person["blocked"] else "Sem turno"
            rows.append(([(stamp-EPOCH).days, WEEKDAYS[stamp.weekday()], label], FREE, 24))
    return rows, [14, 13, 33, 27, 20, 21, 11], ["A1:G1", "A2:G2"], (0, 4)


def coverage_sheet(model, report):
    rows = [
        (["Cobertura por função e horário"], TITLE, 30),
        (["Cada linha reúne intervalos consecutivos com os mesmos números. Priorize as linhas com falta mínima."], BODY, 31),
        (["Data", "Início", "Fim", "Função", "Mínimo", "Desejado", "Escalado", "Falta mínima"], HEADER, 25),
    ]
    groups = []
    for t, role, low, want, actual, missing in sorted(report["coverage"], key=lambda r: (r[0]//96, r[1], r[0])):
        values = [role, low, want, actual, missing]
        if groups and groups[-1][1] == t and groups[-1][0]//96 == t//96 and groups[-1][2:] == values:
            groups[-1][1] += 1
        else:
            groups.append([t, t+1, *values])
    for start, end, *values in sorted(groups):
        stamp = model.start + timedelta(days=start//96)
        end_text = "24:00" if end % 96 == 0 else time_text(end)
        rows.append(([(stamp-EPOCH).days, time_text(start), end_text, *values], ALERT if values[-1] else BODY, 22))
    return rows, [15, 12, 12, 23, 12, 13, 12, 17], ["A1:H1", "A2:H2"], (0, 3)


def styles():
    fonts = [(11, "14253C", False), (17, "FFFFFF", True), (11, "FFFFFF", True), (11, "263D59", True), (11, "80351A", False)]
    font_xml = "".join(f'<font>{"<b/>" if bold else ""}<sz val="{size}"/><color rgb="FF{color}"/><name val="Calibri"/></font>'
                       for size, color, bold in fonts)
    colors = ["142B4A", "204879", "F0F5FC", "F1F3F6", "FFF0E7", "E4EFFC"]
    fill_xml = '<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    fill_xml += "".join(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{color}"/><bgColor indexed="64"/></patternFill></fill>'
                        for color in colors)
    specs = [(0, 0, 0), (1, 2, 0), (2, 3, 0), (0, 4, 0), (0, 5, 0),
             (4, 6, 0), (0, 0, 164), (3, 7, 0)]
    formats = "".join(f'<xf numFmtId="{fmt}" fontId="{font}" fillId="{fill}" borderId="0" xfId="0" '
                      f'applyNumberFormat="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
                      for font, fill, fmt in specs)
    return (f'<styleSheet xmlns="{MAIN}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
            f'<fonts count="{len(fonts)}">{font_xml}</fonts><fills count="{len(colors)+2}">{fill_xml}</fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            f'<cellXfs count="{len(specs)}">{formats}</cellXfs><cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def sheet_xml(sheet, date_column=False):
    rows, widths, merged, (x, y) = sheet
    cols = "".join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate(widths, 1))
    pane = "bottomRight" if x else "bottomLeft"
    split = f'xSplit="{x}" ' if x else ""
    top = chr(65 + x) + str(y + 1)
    xml_rows = []
    for number, (row, style, height) in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row):
            ref = chr(65 + column) + str(number)
            date_cell = date_column and column == 0 and isinstance(value, int)
            cell_style = DAY if date_cell else FREE if value in ("Sem turno", "Indisponível") else style
            prefix = f'<c r="{ref}" s="{cell_style}"'
            if isinstance(value, (float, int)):
                cells.append(f'{prefix}><v>{value}</v></c>')
            else:
                cells.append(f'{prefix} t="inlineStr"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>')
        xml_rows.append(f'<row r="{number}" ht="{height}" customHeight="1">{"".join(cells)}</row>')
    merges = "".join(f'<mergeCell ref="{ref}"/>' for ref in merged)
    orientation = "landscape" if x else "portrait"
    return (f'<worksheet xmlns="{MAIN}"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
            f'<sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane {split}ySplit="{y}" topLeftCell="{top}" '
            f'activePane="{pane}" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols>'
            f'<sheetData>{"".join(xml_rows)}</sheetData><mergeCells count="{len(merged)}">{merges}</mergeCells>'
            f'<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
            f'<pageSetup paperSize="9" orientation="{orientation}" fitToWidth="1" fitToHeight="0"/></worksheet>')


def xlsx(model, report):
    assignments, continuation = schedule_rows(model, report)
    tabs = [("Gerencial", manager_sheet(model, report, assignments, continuation), False),
            ("Cobertura", coverage_sheet(model, report), True)]
    used = {"gerencial", "cobertura", "history"}
    tabs.extend((unique_tab(person["name"], used), employee_sheet(model, p, assignments, continuation), True)
                for p, person in enumerate(model.people))
    sheets, overrides, relationships = [], [], []
    book_type = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as file:
        for i, (name, sheet, date_column) in enumerate(tabs, 1):
            path = f"worksheets/sheet{i}.xml"
            sheets.append(f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>')
            overrides.append(f'<Override PartName="/xl/{path}" ContentType="{book_type}.worksheet+xml"/>')
            relationships.append(f'<Relationship Id="rId{i}" Type="{OFFICE}/worksheet" Target="{path}"/>')
            file.writestr(f"xl/{path}", sheet_xml(sheet, date_column))
        file.writestr("[Content_Types].xml", f'<Types xmlns="{CONTENT}">'
                      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                      '<Default Extension="xml" ContentType="application/xml"/>'
                      f'<Override PartName="/xl/workbook.xml" ContentType="{book_type}.sheet.main+xml"/>'
                      f'<Override PartName="/xl/styles.xml" ContentType="{book_type}.styles+xml"/>{"".join(overrides)}</Types>')
        file.writestr("_rels/.rels", f'<Relationships xmlns="{REL}">'
                      f'<Relationship Id="rId1" Type="{OFFICE}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        file.writestr("xl/workbook.xml", f'<workbook xmlns="{MAIN}" xmlns:r="{OFFICE}">'
                      f'<bookViews><workbookView activeTab="0"/></bookViews><sheets>{"".join(sheets)}</sheets></workbook>')
        file.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{REL}">{"".join(relationships)}'
                      f'<Relationship Id="rIdStyles" Type="{OFFICE}/styles" Target="styles.xml"/></Relationships>')
        file.writestr("xl/styles.xml", styles())
    return buffer.getvalue()
