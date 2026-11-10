"""Local scheduling model, using integer 15-minute slots in São Paulo civil time."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import random

ROLES = ["Cozinha", "Atendimento", "Caixa", "Limpeza"]
CLT = "https://www2.camara.leg.br/legin/fed/declei/1940-1949/decreto-lei-5452-1-maio-1943-415500-normaatualizada-pe.pdf"
EC = "https://www2.camara.leg.br/legin/fed/emecon/2026/emendaconstitucional-141-16-outubro-2026-800062-publicacaooriginal-181622-pl.html"
RULESET = "sp-simulacao-0.1"

def demo():
    names = ["Ana", "Bruno", "Carla", "Davi", "Elisa", "Fábio", "Gabi", "Hugo",
             "Iara", "João", "Lia", "Mauro", "Nina", "Otávio", "Paula"]
    roles = [0]*5 + [1]*4 + [2]*3 + [3]*3
    people = [
        dict(name=name + " Demo", skills=[ROLES[role]] + (["Caixa"] if i == 6 else []),
             team=["A", "B", "C", ""][i % 4], blocked=[1] if i == 1 else list(range(7)) if i == 8 else [],
             fixed={0: 0, 5: 1}.get(i), rest="juntas" if i % 3 == 0 else "separadas",
             regime="integral", hours=40)
        for i, (name, role) in enumerate(zip(names, roles))
    ]
    shifts = [
        dict(name="Pré-preparo", start="08:00", end="12:00", pause_start="", pause_end=""),
        dict(name="Almoço", start="12:00", end="16:00", pause_start="", pause_end=""),
        dict(name="Jantar", start="16:00", end="20:00", pause_start="", pause_end=""),
    ]
    demand = [dict(shift=s, role=r, minimum=1, target=2 if s == 1 and r in ROLES[:2] else 1)
              for s, roles in enumerate((["Cozinha", "Limpeza"], ROLES, ROLES[:3])) for r in roles]
    return dict(unit="Bistrô Alameda", start="2026-11-16", days=7, phase=40,
                people=people, shifts=shifts, demand=demand)

def slot(value):
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Horário inválido.")
    h, m = map(int, parts)
    if not (0 <= h < 24 and m in (0, 15, 30, 45)):
        raise ValueError("Use horários em múltiplos de 15 minutos.")
    return h * 4 + m // 15

def shift_slots(shift):
    start, end = slot(shift["start"]), slot(shift["end"])
    if end <= start:
        end += 96
    work = set(range(start, end))
    pause = 0
    if shift["pause_start"] or shift["pause_end"]:
        p, q = slot(shift["pause_start"]), slot(shift["pause_end"])
        p += 96 if p < start else 0
        q += 96 if q < p else 0
        if not start < p < q < end:
            raise ValueError("A pausa precisa ficar dentro do turno.")
        pause = q - p
        work.difference_update(range(p, q))
    duration = len(work)
    if duration > 32 or (duration > 24 and pause < 4) or (16 < duration <= 24 and pause < 1):
        raise ValueError("Turno fora do perfil ordinário simulado de 8h/dia ou com pausa insuficiente.")
    return start, end, sorted(work)

class Model:
    def __init__(self, data):
        self.data = data
        self.start = date.fromisoformat(data["start"])
        self.days = data["days"]
        self.people = data["people"]
        self.shifts = list(map(shift_slots, data["shifts"]))
        if self.start.year not in range(2025, 2031):
            raise ValueError("O calendário demonstrativo aceita datas de 2025 a 2030.")
        if self.days not in (7, 14, 21, 28) or data["phase"] not in (44, 42, 40):
            raise ValueError("Escolha um ciclo e uma hipótese de jornada da lista.")
        if not 1 <= len(self.people) <= 100 or not 1 <= len(self.shifts) <= 12 or len(data["demand"]) > 48:
            raise ValueError("Use de 1 a 100 pessoas, 1 a 12 turnos e até 48 linhas de demanda.")
        for person in self.people:
            if not person["name"].strip() or not set(person["skills"]) <= set(ROLES):
                raise ValueError("Confira nome e funções de cada pessoa.")
            if person["fixed"] is not None and not 0 <= person["fixed"] < len(self.shifts):
                raise ValueError("Confira o turno fixo de cada pessoa.")
            if not 1 <= person["hours"] <= 44:
                raise ValueError("Jornada contratual deve estar entre 1 e 44 horas.")
        self.requirements = {}
        for row in data["demand"]:
            role, shift = row["role"], row["shift"]
            minimum, target = row["minimum"], row["target"]
            if role not in ROLES or not 0 <= shift < len(self.shifts) or not 0 <= minimum <= target <= 100:
                raise ValueError("Revise turno, função e quantidades da demanda.")
            start, end, _ = self.shifts[shift]
            weekdays = row.get("weekdays", list(range(7)))
            if not isinstance(weekdays, list) or any(type(d) is not int or not 0 <= d < 7 for d in weekdays):
                raise ValueError("Confira os dias da semana da cobertura.")
            for day in range(self.days):
                if (self.start.weekday() + day) % 7 not in weekdays:
                    continue
                for t in range(day * 96 + start, day * 96 + end):
                    previous = self.requirements.get((t, role), (0, 0))
                    self.requirements[t, role] = max(previous[0], minimum), max(previous[1], target)
        self.jobs = []
        for day in range(self.days):
            for role in ROLES:
                for shift, (_, _, work) in enumerate(self.shifts):
                    if any(self.requirements.get((day * 96 + t, role), (0, 0))[1] for t in work):
                        self.jobs.append((day, shift, role))

    def eligible(self, person, job):
        day, shift, role = job
        end = self.shifts[shift][1]
        return (person["regime"] == "integral" and role in person["skills"]
                and person["fixed"] in (None, shift)
                and all(d not in person["blocked"] for d in range(day, day + (end-1)//96 + 1)))

    def interval(self, job):
        day, shift, _ = job
        start, end, work = self.shifts[shift]
        return day * 96 + start, day * 96 + end, [day * 96 + t for t in work]

    def conflicts(self, person, jobs):
        intervals = sorted(self.interval(job) for job in jobs)
        if any(b[0] - a[1] < 44 for a, b in zip(intervals, intervals[1:])):
            return "Interjornada abaixo de 11h", "CLT art. 66", CLT
        hours = Counter(t // 96 for _, _, work in intervals for t in work)
        if any(h > 32 for h in hours.values()):
            return "Mais de 8h trabalhadas no dia civil", "Limite ordinário do cenário", EC
        limit = min(person["hours"], self.data["phase"]) * 4
        max_days = 6 if self.data["phase"] == 44 else 5
        for first in range(-6, self.days + 1):
            days = [hours[d] for d in range(first, first + 7)]
            if sum(days) > limit or sum(h > 0 for h in days) > max_days:
                return "Limite de jornada ou de dias trabalhados em janela móvel de 7 dias", "Premissa conservadora da simulação", EC
        return None

    def report(self, assignments):
        coverage, per_person = Counter(), defaultdict(list)
        counted = set()
        findings = []
        for entry in assignments:
            p, day, shift, role = entry
            if not 0 <= p < len(self.people) or not 0 <= day < self.days or not 0 <= shift < len(self.shifts) or role not in ROLES:
                raise ValueError("Alocação inválida.")
            job = (day, shift, role)
            per_person[p].append(job)
            person = self.people[p]
            if not self.eligible(person, job):
                findings.append(dict(person=person["name"], message="Função, disponibilidade, turno fixo ou regime incompatível.",
                                     clause="Configuração da pessoa", source=None))
                continue
            _, _, work = self.interval(job)
            for t in work:
                if (p, t) not in counted:
                    counted.add((p, t))
                    coverage[t, role] += 1
        for p, jobs in per_person.items():
            conflict = self.conflicts(self.people[p], jobs)
            if conflict:
                message, clause, source = conflict
                findings.append(dict(person=self.people[p]["name"], message=message, clause=clause, source=source))
        rows, minimum, deficit, desired = [], 0, 0, 0
        for (t, role), (need, want) in sorted(self.requirements.items()):
            staffed = coverage[t, role]
            missing = max(0, need - staffed)
            minimum += need
            deficit += missing
            desired += max(0, want - staffed)
            rows.append([t, role, need, want, staffed, missing])
        return dict(assignments=assignments, coverage=rows, deficit=deficit, minimum=minimum, desired=desired,
                    findings=findings, legal="PENDING_LEGAL_REVIEW", ruleset=RULESET,
                    unsupported=[p["name"] for p in self.people if p["regime"] != "integral"])

    def solve(self):
        results = []
        rng = random.Random(141)
        candidates = {job: [p for p, person in enumerate(self.people) if self.eligible(person, job)]
                      for job in self.jobs}
        potential = defaultdict(set)
        for job, people in candidates.items():
            for t in self.interval(job)[2]:
                potential[t, job[2]].update(people)
        structural = sum(max(0, low - len(potential[key])) for key, (low, _) in self.requirements.items())
        for attempt in range(18):
            by_person, coverage = defaultdict(list), Counter()
            assignments = []
            jobs = sorted(self.jobs, key=lambda j: len(candidates[j]) + rng.random() * 4)
            work_slots = {job: self.interval(job)[2] for job in jobs}
            for level in (0, 1):
                for day, shift, role in jobs:
                    job = (day, shift, role)
                    slots = work_slots[job]
                    people = sorted(candidates[job], key=lambda p: self.preference(p, job, by_person[p], attempt, rng))
                    for p in people:
                        if not any(coverage[t, role] < self.requirements.get((t, role), (0, 0))[level] for t in slots):
                            break
                        if self.conflicts(self.people[p], by_person[p] + [job]):
                            continue
                        by_person[p].append(job)
                        assignments.append((p, *job))
                        for t in slots:
                            coverage[t, role] += 1
            results.append(self.report(sorted(assignments)))
        results.sort(key=lambda r: (r["deficit"], r["desired"], len(r["assignments"])))
        distinct = []
        for result in results:
            if result["deficit"] != results[0]["deficit"]:
                break
            if all(result["assignments"] != other["assignments"] for other in distinct):
                distinct.append(result)
            if len(distinct) == 3:
                break
        return dict(scenarios=distinct, structural=structural, attempts=18, seed=141)

    def preference(self, p, job, previous, attempt, rng):
        day = job[0]
        person = self.people[p]
        adjacent = any(abs(day - old[0]) == 1 for old in previous)
        rest = (-0.6 if person["rest"] == "juntas" else 0.6) if adjacent else 0
        sunday = (self.start + timedelta(days=day)).weekday() == 6
        prior_sundays = sum((self.start + timedelta(days=old[0])).weekday() == 6 for old in previous)
        balance = (2 * prior_sundays if sunday else 0) + rest
        return len(previous) + balance + rng.random() * (1 + attempt % 4)


