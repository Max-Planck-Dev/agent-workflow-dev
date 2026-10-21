# Plan: Feeling Lucky — ahorro de tokens y tiempo por story

## Summary
Recortar el costo de `/maxPlanck-feeling-lucky` (y de `/maxPlanck-change`, que comparte agentes) sin perder garantías:
- El plan-review pasa a 1 ronda. La 2ª solo ocurre si la 1ª trajo CRITICAL/HIGH, y lo decide el helper.
- El design-review tiene un tope de 2 rondas.
- El Tech Lead referencia el plan PRP de la story en vez de transcribirlo, y los reviewers reciben ese PRP.
- Por story se verifica con `Check` (typecheck + lint) y `Test (focused)`. El orquestador confía en la línea `VERDICT` del Developer y ya no re-corre builds.
- El build completo corre una vez, en un gate de integración helper-driven antes del audit. La suite completa queda en QA, que ya la corre.
- El orquestador rutea leyendo solo las líneas que deciden.
- Todos los loops bajan de 3 a 2 intentos.

## User Story
Como usuario del workflow, quiero que el pipeline completo gaste menos tokens y minutos por story, para correr sprints enteros sin pagar rondas de revisión y builds repetidos que no cambian el resultado.

## Problem → Solution
- Plan-review hasta 3 rondas por story → 1 ronda, más 1 solo si hubo CRITICAL/HIGH. `RECHECK` lo calcula `plan_review.py`.
- El story plan transcribe el PRP → el story plan mapea AC → tasks del PRP. El PRP es parte del plan efectivo: se revisa en plan-review y se le pasa al code review.
- Build + tests por story, y el orquestador los repite → Developer: `Check` + `Test (focused)` y una línea `VERDICT` por componente. Orquestador: lee esas líneas. Build: una vez, en `integration_gate.py`.
- Design-review hasta 3 rondas → tope de 2.
- El orquestador lee reportes enteros → `grep`/`awk` de las líneas de veredicto y de los headings.
- Loop protection: 3 → 2.

## Metadata
- **Complexity**: Large (2 helpers modificados + 1 helper nuevo + tests + prosa de 8 agentes/skills)
- **Source PRD**: N/A
- **PRD Phase**: N/A
- **Estimated Files**: 18

---

## UX Design
Internal change — no user-facing UX transformation. No se toca el dashboard: el gate no es una fase propia, y su resultado viaja en el `Reason:` de las líneas `PIPELINE` y en una línea `Integration gate (...)` que no empieza con `Phase`, así que el parser no la toma. Contra: mientras el gate corre, el dashboard muestra la fase anterior.

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `.claude/skills/maxPlanck-feeling-lucky/SKILL.md` | 1-150 | Orquestador: routing, loop protection, state JSON |
| P0 | `.claude/skills/maxPlanck-plan-review/plan_review.py` | 52-233, 286-311, 361-377, 564-648 | Constantes, prompt, `state()`, `review_docs()`, link guards, `file_round()` |
| P0 | `.claude/skills/maxPlanck-review/code_review.py` | 71, 89, 242-262, 377-479 | `components()`, `trusted_roots`, `doc_files()` (planes del sprint) |
| P0 | `.claude/agents/maxPlanck-tech-lead.md` | 64-117 | Story Plan Format y propuestas |
| P0 | `.claude/agents/maxPlanck-developer.md` | 23-52 | Checklist y verificación |
| P1 | `.claude/skills/maxPlanck-develop/SKILL.md` | 23-51 | Pasos, Implementation Order, criterios |
| P1 | `.claude/agents/maxPlanck-architect.md` | 83-97, 168 | Template `## Build & Run Commands` |
| P1 | `.claude/maxPlanck-default-stack.md` | 30-38 | Comandos del stack por defecto |
| P1 | `.claude/skills/maxPlanck-change/SKILL.md` | 29-45 | Mismos loops: alinear |
| P1 | `tests/test_plan_review.py`, `tests/test_code_review.py`, `tests/helpers.py` | all | Fixtures (`FAKE_CODEX`, `load_module`), estilo |
| P2 | `.claude/agents/maxPlanck-product-owner.md` | 30-64 | Story Format |
| P2 | `.claude/skills/maxPlanck-plan/SKILL.md`, `.claude/skills/maxPlanck-plan-review/SKILL.md` | all | Pasos y criterios |
| P2 | `.claude/agents/maxPlanck-qa-tester.md`, `.claude/skills/maxPlanck-test/SKILL.md` | test run | Confirmar que QA ya corre la suite completa |
| P2 | `bin/pipeline_dashboard.py` | 60-100 | `ROUTE_RE`/`SKIP_RE`: confirmar que la línea del gate no matchea |
| P2 | `tests/replay.py` | 1-25 | Uso real: `replay.py <fixture> <target> --delay 0` |
| P2 | `setup.sh` | skill copy | Confirmar que copia todos los archivos de cada skill dir (el helper nuevo viaja solo) |
| P2 | `.claude/CLAUDE.md` | flujo, ownership, DoD | Documentación |

## External Documentation

| Topic | Source | Key Takeaway |
|---|---|---|
| Vitest | `vitest related <files> --run` | Solo los tests que importan esos archivos. Con `CI=1` no entra en watch |
| Jest | `--findRelatedTests <files>` | Equivalente. `--passWithNoTests` evita el fallo cuando no hay tests relacionados |
| TypeScript | `tsc --noEmit -p <tsconfig>` | Sin emisión (a diferencia de `tsc -b`, que escribe `.tsbuildinfo`) |
| npx | `npx --no-install` | Falla en vez de descargar un binario que no está instalado |

---

## Patterns to Mirror

### HELPER_STATE (la ruta la decide el helper)
// SOURCE: plan_review.py:214-229
```python
def state(report: str, plan: str, sprint: str, story: str) -> dict:
    decided = decisions(plan)
    proposals = filed(report, sprint, story)
    history = rounds(report)
    ...
```

### HELPER_OUTPUT (KEY=VALUE + exit codes 0/2/3/4)
// SOURCE: plan_review.py:36-37, 638-647
```python
print(f"VERDICT={after['verdict']}")
print(f"OPEN={','.join(after['open'])}")
```

### DOC_LINK_GUARD
// SOURCE: plan_review.py:304-307, 361-376
```python
if os.path.isfile(index) and doc_link_ok(index, roots):
    found.append(os.path.relpath(index, root))
```

### COMPONENTS_TABLE (parseo de la arquitectura, con fallback `app` / `.`)
// SOURCE: plan_review.py:325-353
```python
def components(architecture: str) -> List[Tuple[str, str]]:
    found = [(unquote(r[0]), unquote(r[1])) for r in table_rows(architecture, "Components", "##") ...]
    ...
    return [("app", ".")]
```

### PRECONDITION
// SOURCE: plan_review.py:610-614
```python
raise Precondition(f"docs/stories/{story}.md does not exist — ...")
```

### ATOMIC_WRITE
// SOURCE: plan_review.py:632-636
```python
partial = ctx["path"] + ".tmp"
with open(partial, "w", encoding="utf-8") as fh:
    fh.write(...)
os.replace(partial, ctx["path"])
```

### ORCHESTRATOR_LOG
// SOURCE: feeling-lucky/SKILL.md:131-134
```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
```

### TEST_STRUCTURE
// SOURCE: tests/test_plan_review.py:1-20, 161-172 (`load_module`, `FAKE_CODEX`, `proposal()`, tmp project)

---

## Decisiones

**Las tomó el usuario:**
1. **PRP ↔ story**: línea `**PRP plan:** .claude/PRPs/plans/<name>.plan.md` en la story. La agrega un humano. El PO la conserva y nunca la inventa.
2. **Plan-review**: 1 ronda, más una 2ª solo si la ronda tuvo CRITICAL/HIGH. Nunca hay una 3ª en el pipeline.
3. **Gate** después de la última story y antes del audit. Si falla → `develop all` → `review all` → gate → audit.
4. **Reintentos a 2** en todos los loops.

**Salieron de la revisión de Codex (ver Notes):**
5. **El PRP es parte del plan efectivo**: el plan-review revisa sus tasks, rutas, comandos, orden y fidelidad a la arquitectura (no el estilo). El code review lo recibe staged.
6. **El gate corre solo Build**, no la suite. QA ya corre la suite completa (`maxPlanck-test` paso 4). Correrla también en el gate la duplicaba, y además antes de que existan los tests de aceptación. "Suite completa al cierre" = QA. "Build al cierre" = gate.
7. **El gate cubre todos los componentes in-scope que no son `infra`**, no los que se infieren de los planes. Es más simple y no deja pasar un componente que un fix pass tocó sin declararlo. Un componente sin línea `Build:` se reporta `SKIP`. Si el resultado es cero componentes construidos → `FAIL`, nunca un PASS vacío.
8. **El gate es un helper** (`integration_gate.py` en el skill dir de feeling-lucky), no grep ad hoc. Corre cada comando con cwd = path del componente, `CI=1`, timeout y exit code preservado. Persiste el reporte en `docs/sprints/sprint-<NN>/integration-gate.md` (owner: orchestrator, igual que `pipeline-state.json`), y ese reporte es el work order de `develop all`.
9. **Los comandos de `## Build & Run Commands` son relativos al directorio del componente, sin `cd`.** Las líneas nuevas del default stack siguen esa convención.
10. **Fast-path, no auto-aceptación**: el Tech Lead acepta LOW/mecánicos tras un chequeo rápido contra arquitectura y filesystem. Puede rechazarlos.
11. **Lo que queda del punto 5 original es bajar los reintentos a 2.** Que el review vuelva solo por findings críticos ya existe (`code_review.py:649`).

## Files to Change

| File | Action | Justification |
|---|---|---|
| `.claude/skills/maxPlanck-plan-review/plan_review.py` | UPDATE | PRP (validado, confinado) en docs + prompt; `recheck` |
| `.claude/skills/maxPlanck-review/code_review.py` | UPDATE | Stagear los PRP declarados por las stories con plan en el sprint |
| `.claude/skills/maxPlanck-feeling-lucky/integration_gate.py` | CREATE | Gate: Build por componente, reporte persistente, KEY=VALUE |
| `tests/helpers.py` | UPDATE | Ruta `INTEGRATION_GATE` para `load_module` |
| `tests/test_plan_review.py` | UPDATE | PRP + recheck |
| `tests/test_code_review.py` | UPDATE | PRP staged |
| `tests/test_integration_gate.py` | CREATE | Tests del gate |
| `.claude/skills/maxPlanck-plan-review/SKILL.md` | UPDATE | `RECHECK`, PRP en cobertura |
| `.claude/agents/maxPlanck-tech-lead.md` | UPDATE | Sección PRP Plan; fast-path; ronda única |
| `.claude/skills/maxPlanck-plan/SKILL.md` | UPDATE | Leer el PRP; criterios |
| `.claude/agents/maxPlanck-product-owner.md` | UPDATE | Línea opcional `**PRP plan:**` |
| `.claude/agents/maxPlanck-developer.md` | UPDATE | Leer el PRP; Check + focused; VERDICT; `integration-gate.md` como work order |
| `.claude/skills/maxPlanck-develop/SKILL.md` | UPDATE | Ídem |
| `.claude/agents/maxPlanck-architect.md` | UPDATE | `Check:` / `Test (focused):`, comandos sin `cd` |
| `.claude/maxPlanck-default-stack.md` | UPDATE | Check/focused por componente |
| `.claude/skills/maxPlanck-adopt/SKILL.md` | UPDATE | Registrar Check/focused si existen |
| `.claude/skills/maxPlanck-feeling-lucky/SKILL.md` | UPDATE | Routing por grep, topes, recheck, gate, VERDICT, reintentos a 2, state |
| `.claude/skills/maxPlanck-change/SKILL.md` | UPDATE | Alinear (recheck, tope de design, gate, retries) |
| `.claude/CLAUDE.md` | UPDATE | Flujo, ownership de `integration-gate.md`, DoD |

## NOT Building

- Cambios de modelos por agente (`/maxPlanck-config`).
- Una fase "gate" en el dashboard o cambios en `bin/pipeline_dashboard.py`.
- Batching de stories y contexto acotado por sección de arquitectura.
- Detección automática del PRP por búsqueda.
- Scripts `npm run check` en los proyectos scaffoldeados (cambiaría el scaffolding).
- Un manifiesto estructurado o run IDs en el VERDICT del Developer: la frescura se toma del slice del log, y el gate es la red de seguridad.
- Un harness ejecutable para la prosa del orquestador (el repo no tiene uno). Se cubre con tests de los helpers y simulación manual.
- Bloquear rondas manuales extra en `plan_review.py`: el tope es de routing, y un humano puede pedir otra ronda.

---

## Step-by-Step Tasks

### Task 1: `plan_review.py`, PRP declarado (validado y confinado)
- **ACTION**: Resolver el PRP de la story y sumarlo a los docs revisados.
- **IMPLEMENT**:
  - `PRP_DIR = os.path.join(".claude", "PRPs", "plans")`, `PRP_LINE_RE = re.compile(r"^\*\*PRP plan:\*\*\s*(.*?)\s*$", re.M)`.
  - `def prp_plan(root: str, story: str) -> Optional[str]`: lee `docs/stories/<story>.md`. Sin línea → `None`. Más de una línea → `Precondition`. El valor sin backticks (`unquote`) debe cumplir: no absoluto, sin segmentos `..`, `normpath` que empiece con `PRP_DIR + os.sep`, termina en `.plan.md`, `realpath(path)` bajo `realpath(root/PRP_DIR)` (cubre symlinks finales e intermedios) y `os.path.isfile`. Si falla → `Precondition(f"docs/stories/{story}.md declares PRP plan {value!r}, which {why} — fix or remove the line")`. Devuelve la ruta relativa normalizada.
  - `review_docs()`: agregar `prp_plan()` justo después de `plan_path`. `load()`: `ctx["prp"]`.
  - `PROMPT`: placeholder `{prp}`. Con PRP: `- {path} — the PRP implementation plan the story plan maps onto: it is part of the plan under review. Check its tasks, file paths, commands, order and fidelity to docs/architecture.md as you check the story plan; a story-plan task that names a PRP task must exist there. Its prose style is not in scope.` Sin PRP: `""`. El criterio 4 (Concreteness) también aplica a las tasks del PRP. `brief()` pasa `prp=`.
- **MIRROR**: DOC_LINK_GUARD, PRECONDITION.
- **GOTCHA**: no escribir `maxPlanck` en el script (`test_script_is_prefix_free`). `stage_docs` copia `os.path.join(stage, rel)`; el `rel` ya validado no sale de `stage`.
- **VALIDATE**: Task 4.

### Task 2: `plan_review.py`, `recheck`
- **IMPLEMENT**:
  - `MAX_ROUNDS = 2`, `RECHECK_SEVERITIES = ("CRITICAL", "HIGH")`.
  - `def latest_severities(report: str, sprint: str, story: str) -> List[str]`: el texto desde el último match de `ROUND_RE`, y las severidades de sus filas de ID válidas (`cells`, el regex de `filed`).
  - `state()`: `"recheck": bool(latest_ok) and len(history) < MAX_ROUNDS and any(s in RECHECK_SEVERITIES for s in latest_severities(...))`. Se cuentan **todas** las rondas: una `unavailable` también consume el tope.
  - `file_round()`: `print(f"RECHECK={'yes' if after['recheck'] else 'no'}")` después de `OPEN=`. `cmd_status` lo incluye vía `state`.
- **GOTCHA**: `verdict` no cambia. Con la última ronda unavailable, `recheck` es falso, y el orquestador mantiene su rama UNAVAILABLE (Task 10), que se decide por `**Latest round:**`, no por `recheck`.
- **VALIDATE**: Task 4.

### Task 3: `code_review.py`, PRP staged
- **IMPLEMENT**: `prp_plan()` con el mismo contrato (copia local: cada helper es standalone y ya duplica `components`/`doc_link_ok`). En `doc_files()`, por cada story con `plans/story-NNN-plan.md` en el sprint, si su story declara un PRP válido se agrega a `found` (sin duplicados). Un PRP inválido acá **no** es precondición (el code review no debe caerse por una línea de story): se omite y el prompt no lo menciona. En el `PROMPT`, sumar a la lista de docs: `- .claude/PRPs/plans/ — the PRP implementation plans some story plans map onto (the story plan's **PRP plan:** line names it); code should implement those tasks too`. El criterio 2 pasa a "the tasks of its plan (and of the PRP plan it maps onto)".
- **GOTCHA**: `sendable()` también se aplica al PRP.
- **VALIDATE**: test en `tests/test_code_review.py`: el PRP declarado aparece en el stage, y uno inválido no aparece pero el run no falla.

### Task 4: tests de `plan_review.py`
- **IMPLEMENT**:
  - `test_prp_plan_named_by_the_story_reaches_codex_and_the_prompt`
  - `test_no_prp_line_means_no_prp_doc_and_no_prompt_line`
  - `test_invalid_prp_line_is_a_precondition`, con subTests: absoluto, `..`, fuera de `PRP_DIR`, sin `.plan.md`, inexistente, symlink final que sale, directorio intermedio symlink que sale, dos líneas → exit 2 `ERROR=`.
  - `test_recheck_only_after_a_round_with_critical_or_high`: HIGH → yes; MEDIUM/LOW → no; sin propuestas → no.
  - `test_recheck_never_after_the_second_round`: ronda 2 con CRITICAL → no.
  - `test_unavailable_round_counts_toward_the_cap`: unavailable y después ok con HIGH → no.
  - `test_status_reports_recheck`
- **VALIDATE**: `python3 -m unittest tests.test_plan_review` (desde `tests/` o con `-s tests`).

### Task 5: `integration_gate.py` (nuevo) + tests
- **ACTION**: helper stdlib-only con el mismo estilo (docstring de uso, exit codes, KEY=VALUE, `Precondition`).
- **IMPLEMENT**:
  - Uso: `python3 integration_gate.py run [--root DIR] [--timeout SECONDS]` y `status`.
  - Lee `docs/sprints/.current-sprint` y `docs/architecture.md`. Componentes = la tabla `## Components` (`ID`, `Path`, `Kind`), sin `Kind == infra`. Sin la sección → `app` / `.` (compatibilidad). `### Excluded Paths` nunca se toca.
  - Comando Build: en `## Build & Run Commands`, la subsección `### <ID>` (heading que empieza con el ID) y su línea `- Build: <cmd>` (backticks quitados). Sin subsecciones y un solo componente → la línea `- Build:` de la sección o de la tabla legacy.
  - Por componente: `subprocess.run(cmd, shell=True, cwd=<path>, env={**os.environ, "CI": "1"}, timeout=..., capture_output=True, text=True, errors="replace")`. `shell=True` es aceptable: el comando sale del doc de arquitectura del proyecto, el mismo que los agentes ya ejecutan por Bash. Resultado: `PASS` (rc 0), `FAIL` (rc≠0), `TIMEOUT`, `SKIP` (sin línea Build), `MISSING` (el path no existe → cuenta como FAIL).
  - Veredicto: `FAIL` si algún componente es FAIL/TIMEOUT/MISSING, o si ninguno fue PASS. Si no, `PASS`.
  - Reporte atómico `docs/sprints/sprint-<NN>/integration-gate.md`: se agrega una sección `## Attempt <k> — <fecha>` (append-only, como las rondas), con una tabla `| Component | Path | Command | Result | Seconds |` y, por cada fallo, las últimas 60 líneas de salida en un bloque de código. Cabecera: `**Verdict:** PASS|FAIL`, `**Attempts:** k`.
  - Stdout: `GATE=PASS|FAIL`, `ATTEMPT=k`, una línea `COMPONENT=<id>:<result>` por componente, `REPORT=<rel path>`. Exit 0 siempre que corrió (el veredicto va en `GATE=`) y 2 en precondición.
  - `status`: JSON `{sprint, attempts, verdict}`.
- **IMPLEMENT** (`tests/helpers.py`): constante `INTEGRATION_GATE`.
- **IMPLEMENT** (`tests/test_integration_gate.py`): proyecto tmp con componentes cuyos Build son `true`/`false`/`sleep 5`:
  - PASS cuando todos pasan
  - FAIL si uno falla, con su tail en el reporte
  - timeout → `TIMEOUT` + FAIL
  - `infra` excluido
  - sin línea Build → `SKIP`, y todos SKIP → FAIL
  - path inexistente → `MISSING` + FAIL
  - sin `## Components` → `app` / `.`
  - el comando corre con cwd del componente y `CI=1` (Build: `pwd > out; echo $CI >> out`)
  - los intentos se agregan sin pisar los anteriores
  - el script no contiene `maxPlanck`
- **GOTCHA**: el helper vive en el skill dir de feeling-lucky. `setup.sh` copia todos los archivos de cada skill (verificarlo), y el rebranding reescribe las referencias. `/maxPlanck-change` lo invoca por la misma ruta.
- **VALIDATE**: `python3 -m unittest discover -s tests`.

### Task 6: plan-review `SKILL.md`
- **IMPLEMENT**: el step 5 loguea `RECHECK`. After Completion / CHANGES PROPOSED: "Run `/maxPlanck-plan` so the Tech Lead rules on each proposal; re-run `/maxPlanck-plan-review` only if this round printed `RECHECK=yes` (it had a CRITICAL or HIGH proposal) — otherwise go on to `/maxPlanck-develop`." En What the Review Covers: el PRP declarado es parte del plan revisado.

### Task 7: Tech Lead + skill `plan` + PO
- **IMPLEMENT** (`maxPlanck-tech-lead.md`):
  - `## PRP Plan`: si la story tiene `**PRP plan:**`, leer ese archivo. No se copian sus snippets, patrones, mandatory reading ni gotchas. Cabecera `**PRP plan:** <path>`. `## Implementation Order` lista el orden de componentes y puede remitir a "the PRP's Step-by-Step Tasks". `## Tasks` = mapeo `| # | Task | Files (create/modify) | Covers AC |` con `PRP Task N — <nombre>` y los archivos del PRP. Se agregan tasks propias solo para ACs que el PRP no cubre. Si choca con la arquitectura, gana la arquitectura y el conflicto se anota en Risks. `**Verification:**` y Risks siguen siendo obligatorios. Los headings `## Implementation Order` y `## Tasks` no pueden faltar (el orquestador los chequea).
  - Propuestas, fast-path: "LOW and mechanical proposals (a typo, a path, a command to copy from the architecture doc, formatting): check them against the architecture doc and the file inventory in one pass, then ACCEPT and apply (`mechanical — applied`) or REJECT with the one-line reason. Spend deliberation on CRITICAL, HIGH and MEDIUM." Y: "Normally there is one review round; a second runs only when the first had a CRITICAL or HIGH proposal, and the pipeline never runs a third — rule as if your decision is final."
- **IMPLEMENT** (`maxPlanck-plan/SKILL.md`): step 2 lee la línea PRP de la story. Step 5 incluye el formato de mapeo. Criterio nuevo.
- **IMPLEMENT** (`maxPlanck-product-owner.md`): línea opcional `**PRP plan:**` en Story Format, con la regla de conservarla y no inventarla.

### Task 8: Architect + default stack + adopt
- **IMPLEMENT** (template del architect):
  ```
  - Build: <command>
  - Test: <command — non-interactive; QA and CI run it>
  - Check: <typecheck + lint, writes nothing — e.g. `npx --no-install tsc --noEmit -p tsconfig.json && npx --no-install eslint src`>
  - Test (focused): <runs only the tests related to the given files; `<files>` marks where the component-relative paths go>
  ```
  Nota fija arriba: "Commands are relative to the component's directory — never prefix them with `cd <path>`." En la regla 9: los usos (Check + focused por story; Build en el gate de integración; Test por QA).
- **IMPLEMENT** (`maxPlanck-default-stack.md`), subsección nueva "Per-component quick checks (run from the component directory)":
  - frontend: Check `npx --no-install tsc --noEmit -p tsconfig.app.json && npm run lint`. Focused `npx --no-install vitest related --run --passWithNoTests <files>`.
  - backend: Check `npx --no-install tsc --noEmit -p tsconfig.json && npx --no-install eslint "src/**/*.ts"` (no `npm run lint`, que en Nest trae `--fix`). Focused `npx --no-install jest --findRelatedTests <files> --passWithNoTests`.
- **IMPLEMENT** (adopt): al verificar comandos, registrar `Check`/`Test (focused)` solo si corren; si no, omitirlos.
- **GOTCHA**: sin `Check:`, el Developer usa `Build:` (compatibilidad). Los proyectos existentes recuperan el ahorro cuando el Architect agrega las líneas en su próxima corrida, porque la regla del template lo pide. Se documenta como limitación.

### Task 9: Developer + skill `develop`
- **IMPLEMENT** (`maxPlanck-developer.md`):
  - Pre-coding 2: con `**PRP plan:**` en el story plan, leer el PRP. Sus tasks, patrones y gotchas son el detalle, y si choca con la arquitectura gana la arquitectura.
  - Pre-coding 6: suma `docs/sprints/sprint-<NN>/integration-gate.md`; si su último attempt es FAIL, arreglar el build de esos componentes es prioridad.
  - Regla de verificación (reemplaza la 9): "Verify each component you changed, from its directory: its `Check` command, then its `Test (focused)` command with the component-relative paths of the files you created or modified (deleted files left out, each path quoted). No `Check` line → run `Build` instead; no `Test (focused)` line → `NONE`. Do not run the full `Build`/`Test` on top — the integration gate builds every component once after the last story, and QA runs the full suites."
  - Regla VERDICT: "Before finishing, log one line per component you changed: `VERDICT | Agent: maxPlanck-developer | <story or all>: <component ID> check PASS|FAIL, focused tests PASS|FAIL|NONE | Output: <component path>`. Fix and re-run until PASS; if one stays FAIL, say so in the final report."
- **IMPLEMENT** (`maxPlanck-develop/SKILL.md`): el paso 1 lee el PRP. El paso 5 suma `integration-gate.md`. Implementation Order 3 = la regla nueva. El paso 9 incluye las líneas VERDICT. Criterio: "every component you changed has a VERDICT line with check PASS".

### Task 10: Orquestador `maxPlanck-feeling-lucky/SKILL.md`
- **IMPLEMENT**:
  1. **`## Reading for Routing`** (nueva, antes de las tablas): "Route from the lines that decide; never read a whole report into this context." Comandos:
     - veredicto, rondas, reviewer: `grep -m1 -E '^\*\*(Verdict|Latest round|Reviewer):\*\*' <report>` (una línea por campo)
     - headings: `grep -cE '^## (Implementation Order|Tasks)\s*$' <plan>` = 2; arquitectura `grep -cE '^## (Data Models|API Endpoints)'`
     - Change Log del sprint: `awk '/^## Change Log/{f=1;next} /^## /{f=0} f' <doc> | grep -cE '^\| *[^|]+ *\| *(Sprint )?<NN> *\|'` ≥ 1
     - stories: `ls docs/stories/story-*.md | wc -l`
     - Developer: `awk` del log desde la última línea `PIPELINE ... routing to develop (<S>)`, `grep 'VERDICT | Agent: maxPlanck-developer | <S>:'`
     - gate: las líneas `GATE=` / `COMPONENT=` del helper
  2. **Design**: "Otherwise → design-review" pasa a "Otherwise, if `grep -c '^## Round '` of the design review report is < 2 → `maxPlanck-design-review`; else → the story loop (`Reason: design-review cap (2 rounds) — round-2 proposals ruled by the Architect`)."
  3. **Plan <S>**: después de verificar headings y propuestas abiertas: sin reporte de plan-review → plan-review. Con reporte: `python3 .claude/skills/maxPlanck-plan-review/plan_review.py status --story <S>`. Si `recheck` es true → plan-review (round 2). Si no → `maxPlanck-develop <S>` (`Reason: proposals ruled, no CRITICAL/HIGH in the round — no re-review` / `plan-review cap reached`).
  4. **Plan-review <S>**: se mantiene la fila actual (APPROVED → develop; CHANGES PROPOSED → plan; UNAVAILABLE → skipped + unresolved → develop).
  5. **Develop <S>**: reemplaza "Actually run each changed component's own build command": "Read the developer's VERDICT lines for `<S>` from this phase's slice of the log. One line per component named in the plan's `**Component(s):**` line, each `check PASS` with focused tests `PASS`/`NONE` → review. A FAIL, or a component without a line → re-run develop (`Reason: <component> check FAIL` / `no VERDICT for <component>`)."
  6. **Integration gate** (después del loop y después de cada `review all` APPROVED): `python3 .claude/skills/maxPlanck-feeling-lucky/integration_gate.py run` (Bash timeout 600000). Loguear `PIPELINE | Agent: orchestrator | Integration gate (sprint <NN>, attempt <k>): <id> PASS, <id> FAIL | Output: docs/sprints/sprint-<NN>/integration-gate.md`. `GATE=PASS` → `maxPlanck-audit`. `GATE=FAIL` → `maxPlanck-develop all` (`Reason: integration gate FAIL — <ids>; work order docs/sprints/sprint-<NN>/integration-gate.md`). Con 2 attempts FAIL → force-advance a audit, append `"integration-gate: FAIL after 2 attempts (<ids>)"` a `unresolved` (next command `/maxPlanck-develop all`). Routing de la última story: `Phase review (<S>) finished → routing to audit | Reason: APPROVED — last story; integration gate PASS`. Si falló: `→ routing to develop | Reason: APPROVED — last story; integration gate FAIL (<ids>)`.
  7. **Fix passes**: `review all` APPROVED → gate → audit (como en el punto 6).
  8. **Loop Protection**: "3 runs" → "2 runs"; "after 3 attempts" → "after 2 attempts". La protección de plan-review queda como red de seguridad (el tope real es `recheck`). Agregar el gate (attempts del helper).
  9. **State JSON**: `"gate": 0` en `phase_runs`, `"gate": null` en `verdicts` (`PASS|FAIL`). Una clave faltante = 0/null (la regla ya existe).
- **GOTCHA**: ninguna salida de build pasa por el contexto principal. Solo las líneas `GATE=`/`COMPONENT=`; los detalles quedan en el reporte para el Developer. La línea `Integration gate (...)` no empieza con `Phase`, así que el parser del dashboard la ignora.

### Task 11: `maxPlanck-change/SKILL.md`, alinear
- **IMPLEMENT**: 2b: "max 1 retry" (tope de 2 rondas). 2d: tras el ruling, re-review solo con `recheck` (mismo `status`). 3: el Developer verifica con check/focused y el orquestador lee su VERDICT como en feeling-lucky. 4b (nuevo): gate `integration_gate.py run` antes de audit/test, con el mismo routing y tope. 4: "max 2 retries" → "max 1 retry".

### Task 12: `.claude/CLAUDE.md`
- **IMPLEMENT**:
  - "Stories are built one at a time": plan-review en 1 ronda (+1 con CRITICAL/HIGH vía `RECHECK`), design-review con tope de 2, verificación rápida por story y gate de integración (Build) antes del audit.
  - Árbol de sprint: `integration-gate.md` (orchestrator).
  - File ownership: el orquestador escribe `pipeline-state.json` e `integration-gate.md` (decirlo explícitamente).
  - DoD: Plan (mapeo a PRP), Plan Review (`RECHECK`), Develop (VERDICT por componente), y un ítem nuevo "Integration gate".
  - Skills: mencionar `integration_gate.py` junto a los otros helpers.

### Task 13: Consistencia cruzada
- **VALIDATE**:
  ```bash
  grep -rnE "3 runs|3 attempts|three (runs|attempts)|third attempt|max 2 retries|Actually run each changed component|after 3" .claude/ README.md QUICKSTART.md
  ```
  Resultado esperado: vacío. Revisar a mano cualquier coincidencia que quede.

### Task 14: Verificación
- **VALIDATE**:
  ```bash
  python3 -m unittest discover -s tests
  T=$(mktemp -d) && python3 tests/replay.py tests/fixtures/agent-workflow.modern.log "$T" --delay 0 && printf '[%s] PIPELINE | Agent: orchestrator | Integration gate (sprint 01, attempt 1): api PASS | Output: docs/sprints/sprint-01/integration-gate.md\n' "$(date '+%F %T')" >> "$T/logs/agent-workflow.log" && python3 bin/pipeline_dashboard.py --cwd "$T" --json >/dev/null && echo dashboard-ok
  ```
  Esperado: suite OK y `dashboard-ok` (la línea del gate no rompe el parser). Confirmar antes el nombre del fixture con `ls tests/fixtures`.

---

## Testing Strategy

| Test | Input | Expected | Edge? |
|---|---|---|---|
| PRP staged (plan) | línea válida | archivo en stage + línea en prompt | no |
| sin PRP | sin línea | nada | no |
| PRP inválido | abs / `..` / fuera / sin sufijo / inexistente / symlink final / dir intermedio / 2 líneas | exit 2 `ERROR=` | sí |
| recheck | HIGH / MEDIUM-LOW / vacío | yes / no / no | no |
| tope | ronda 2 CRITICAL; unavailable + ok HIGH | no / no | sí |
| status | — | JSON con `recheck` | no |
| PRP staged (code) | válido / inválido | incluido / omitido sin fallar | sí |
| gate | pass / fail / timeout / infra / skip / all-skip / missing / legacy / cwd+CI / append | ver Task 5 | sí |

### Edge Cases Checklist
- [x] Story sin línea PRP
- [x] Ruta PRP maliciosa / symlinks
- [x] Ronda sin propuestas / unavailable
- [x] Arquitectura sin `Check:` / sin `## Components`
- [x] Gate con cero componentes construibles
- [x] `pipeline-state.json` viejo

---

## Validation Commands

### Static / Unit / Full suite
```bash
cd /Users/admin/Projects/agent-workflow-dev && python3 -m unittest discover -s tests
```
Esperado: OK (baseline 203 + nuevos).

### Dashboard
Ver Task 14. Esperado: `dashboard-ok`.

### Consistencia
Ver Task 13. Esperado: vacío.

### Manual Validation
- [ ] Simular con la prosa: story con propuestas solo LOW → ruling → develop (sin 2ª ronda); con un HIGH → ruling → 2ª ronda → ruling → develop.
- [ ] Design: 2 rondas CHANGES PROPOSED → ruling → story loop.
- [ ] Última story APPROVED → gate FAIL → develop all → review all → gate PASS → audit.

---

## Acceptance Criteria
- [ ] `RECHECK` calculado por el helper, con tope de 2 rondas totales, y con tests
- [ ] PRP validado (realpath) en plan-review y staged en code-review, con tests
- [ ] `integration_gate.py` con tests; reporte persistente; FAIL sin PASS vacío
- [ ] Tech Lead mapea al PRP; fast-path para LOW/mecánicos
- [ ] Developer: Check + focused + VERDICT; el orquestador no re-corre builds
- [ ] Design-review con tope de 2; reintentos a 2; rama UNAVAILABLE intacta
- [ ] Routing por grep documentado
- [ ] `/maxPlanck-change` alineado; CLAUDE.md al día
- [ ] Suite verde + dashboard-ok + grep de consistencia vacío

## Completion Checklist
- [ ] Prosa coherente agente ↔ skill ↔ orquestadores ↔ CLAUDE.md
- [ ] Python: type hints, stdlib, sin `maxPlanck` en los scripts, escrituras atómicas
- [ ] Sin cambios en el dashboard
- [ ] Self-contained

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| El Developer reporta PASS sin correr los comandos | Media | Medio | El gate construye todo antes del audit; los VERDICT quedan en el log |
| Errores de integración entre stories detectados recién en el gate | Media | Medio | `develop all` con `integration-gate.md` como work order |
| Un MEDIUM del plan-review no se re-revisa | Baja | Medio | El Tech Lead lo decide; el code review ve el resultado |
| Proyectos existentes sin `Check:` → Build por story (menos ahorro) | Alta | Bajo | Compatibilidad; el Architect agrega las líneas en su próxima corrida |
| Un componente con build largo agota el timeout del Bash del orquestador | Baja | Medio | `--timeout` por comando < 600 s total; TIMEOUT = FAIL explícito |
| `shell=True` sobre un comando del doc | Baja | Bajo | Es el mismo comando que los agentes ya corren por Bash; viene de un doc del proyecto, no de un input externo |

## Notes
- Los ahorros citados (≈8 min/story en plan-review, 4-6 min por el PRP, 5-10 min en verificación, 5 min/sprint en design) son estimaciones del usuario, no medidas.
- El timeout total del gate tiene que entrar en el techo de 10 min del Bash tool. Default por comando: 300 s. Si hay muchos componentes, el orquestador lo puede llamar con `--timeout` menor. Documentarlo en el docstring.

### Codex Review
- **Corrida**: 2026-10-21 — ok (codex exec, read-only; crítica en `feeling-lucky-token-savings.codex-review.md`)
- **Aplicadas**:
  - #1 (CRITICAL) El PRP se revisa como parte del plan → Task 1 (prompt) y Decisión 5.
  - #2 (HIGH) El code review no veía el PRP → Task 3 nueva.
  - #3 (HIGH) Tope sobre el total de rondas → Task 2 (`len(history)`) + test unavailable→HIGH.
  - #4 (HIGH) Rama UNAVAILABLE → Task 10.4 la conserva explícitamente.
  - #5 (CRITICAL) Selección de componentes del gate → helper, todos los componentes no-infra, cero construidos = FAIL (Decisiones 7-8, Task 5).
  - #6 (HIGH) `cd` vs cwd del componente → comandos sin `cd` (Decisión 9, Task 8).
  - #7 (HIGH) `tsc -b` escribe / `npx` descarga → `tsc --noEmit -p`, `npx --no-install`.
  - #8 (HIGH) Tests interactivos → `CI=1` + timeout en el helper.
  - #9 (HIGH) Suite duplicada con QA → el gate corre solo Build (Decisión 6).
  - #10 (HIGH) Log en `$TMPDIR` → `integration-gate.md` persistente como work order.
  - #11 (HIGH) Confinamiento con `realpath` → Task 1.
  - #12 (MEDIUM) Múltiples líneas PRP → precondición.
  - #14 (MEDIUM) `<files>` → paths relativos al componente, entre comillas, sin borrados.
  - #15 (MEDIUM) Auto-aceptación amplia → fast-path con REJECT posible.
  - #16 (HIGH) Estado del gate → PASS/FAIL, 2 attempts, force-advance + unresolved.
  - #17 (MEDIUM) Exit status → lo maneja `subprocess` en el helper.
  - #18 (MEDIUM) Change Log por grep → `awk` acotado a la sección + columna Sprint.
  - #20 (MEDIUM) `replay.py` mal especificado → comando real + `--json` (Task 14).
  - #21 (LOW) Greps de consistencia → unificados y ampliados (Task 13).
  - Mejora 20 (orden) → helpers y tests antes que la prosa.
- **Descartadas**:
  - #13 (HIGH) VERDICT con run ID / comandos / manifiesto. Parcial: la frescura sale del slice del log y el conjunto esperado del `**Component(s):**` del plan. Un manifiesto estructurado agrega costo de tokens por story (justo lo que se quiere bajar), y el gate es la red de seguridad.
  - #19 (HIGH) Tests de orquestación. Parcial: el repo no tiene harness para la prosa de skills; la lógica que decide se movió a helpers testeados (`recheck`, gate) y el resto queda en simulación manual.
  - #22 (MEDIUM) Migración obligatoria de arquitecturas sin `Check:`. Fuera de alcance: un cambio de docs vivos sin pedido del usuario. Queda como limitación documentada.
  - Mejora 3, parte "rechazar rondas manuales extra": el tope es de routing, y bloquear a un humano que pide otra ronda empeora la UX.
  - Mejora 8, parte "scripts `npm run check`": cambiaría el scaffolding del stack por defecto (NOT Building).
