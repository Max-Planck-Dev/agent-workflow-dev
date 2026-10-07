# Implementation Report: Fase `maxPlanck-design-review` (Codex revisa el diseño; Claude como fallback)

## Summary

Se agregó la fase `design-review` después de `design`: agente `maxPlanck-design-reviewer`, skill `maxPlanck-design-review` y el script determinista `design_review.py` (ronda, IDs `DR-NN-n`, propuestas abiertas, veredicto). Codex revisa si está instalado y funciona; si no, revisa el propio agente. El Architect decide cada propuesta en `## Design Review Log`. Orquestadores, Scrum Master, dashboard, manifest, instalador y docs quedaron cableados.

## Assessment vs Reality

| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Large | Large en alcance, baja en riesgo: los assets ya estaban verificados |
| Confidence | — (no declarada) | Alta para el código testeado; el comportamiento del agente queda sin validar |
| Files Changed | 20 (5 nuevos, 15 modificados) | 20 (5 nuevos, 15 modificados) |

## Tasks Completed

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Script `design_review.py` y tests | Complete | RED → GREEN. Desvío posterior por el code review (ver abajo) |
| 2 | Agente `maxPlanck-design-reviewer` | Complete | |
| 3 | Skill `maxPlanck-design-review` | Complete | |
| 4 | Architect — evaluar propuestas | Complete | `grep -c 'Design Review Log'` da 4 líneas (el plan esperaba ≥ 5: cuenta líneas, no apariciones; el contenido es el del plan) |
| 5 | Skill `maxPlanck-design` | Complete | |
| 6 | Orquestador `feeling-lucky` | Complete | Desvío en el chequeo en shell (ver abajo) |
| 7 | Orquestador `change` | Complete | |
| 8 | Scrum Master y skill `sprint` | Complete | `grep 'Design Review'` da 3 líneas (el plan esperaba ≥ 4); las 5 ediciones están aplicadas |
| 9 | Tests del dashboard (RED) | Complete | 7 fallas esperadas |
| 10 | Dashboard (GREEN) | Complete | |
| 11 | Test de cableado (RED) | Complete | 5 OK, 2 FAIL, como predijo el plan |
| 12 | Manifest del plugin | Complete | |
| 13 | Instalador (GREEN) | Complete | |
| 14 | `.claude/CLAUDE.md` | Complete | `grep -c 'design-review'` da 5 líneas (el plan esperaba ≥ 6); las 7 ediciones están aplicadas |
| 15 | README y QUICKSTART | Complete | |

## Validation Results

| Level | Status | Notes |
|---|---|---|
| Static Analysis | Pass | `bash -n setup.sh`, `ast.parse` de los `.py`, JSON del manifest, sin `__pycache__` en skills. El repo no tiene linter ni type-checker |
| Unit Tests | Pass | 104 tests (62 previos + 42 nuevos) |
| Build | N/A | No hay build |
| Integration | Pass | Install con `--prefix acme` sin restos del prefijo; fallback de punta a punta por CLI sin Codex; `pipeline_dashboard.py --once` |
| Edge Cases | Pass (automatizados) | Los tres ítems manuales del plan siguen pendientes |

No se validó: una corrida real contra Codex, ni la Manual Validation del plan (transición exit 3 → `brief` → `file` hecha por el agente, calidad de su revisión, 3 rondas con force-advance, `/maxPlanck-feeling-lucky` completo).

## Files Changed

| File | Action | Lines |
|---|---|---|
| `.claude/skills/maxPlanck-design-review/design_review.py` | CREATED | +522 |
| `.claude/skills/maxPlanck-design-review/SKILL.md` | CREATED | +86 |
| `.claude/agents/maxPlanck-design-reviewer.md` | CREATED | +121 |
| `tests/test_design_review.py` | CREATED | +363 |
| `tests/test_wiring.py` | CREATED | +81 |
| `tests/helpers.py` | UPDATED | +1 |
| `.claude/agents/maxPlanck-architect.md` | UPDATED | +33 |
| `.claude/skills/maxPlanck-design/SKILL.md` | UPDATED | +11 / -5 |
| `.claude/skills/maxPlanck-feeling-lucky/SKILL.md` | UPDATED | +19 / -5 |
| `.claude/skills/maxPlanck-change/SKILL.md` | UPDATED | +1 |
| `.claude/agents/maxPlanck-scrum-master.md` | UPDATED | +3 / -2 |
| `.claude/skills/maxPlanck-sprint/SKILL.md` | UPDATED | +2 / -1 |
| `bin/pipeline_dashboard.py` | UPDATED | +8 / -3 |
| `tests/test_parser.py` | UPDATED | +90 / -2 |
| `tests/test_render.py` | UPDATED | +15 / -1 |
| `.claude-plugin/plugin.json` | UPDATED | +2 / -1 |
| `setup.sh` | UPDATED | +2 / -1 |
| `.claude/CLAUDE.md` | UPDATED | +11 / -6 |
| `README.md` | UPDATED | +10 / -3 |
| `QUICKSTART.md` | UPDATED | +10 / -7 |

## Deviations from Plan

1. **`design_review.py` ya no es idéntico al asset.** WHAT: función nueva `prose()`; el summary de una ronda se escribe con `\` adelante cuando empieza con `#` o `|`. WHY: hallazgo MEDIUM del code review — el plan pedía no tocar el script, pero el bug era reproducible. El asset en `design-review-codex.assets/` quedó sin el fix.
2. **Chequeo en shell de `feeling-lucky`**: `grep -E '…(ACCEPTED|PARTIAL|REJECTED)'` → `grep -iE '…(ACCEPTED|PARTIAL|REJECTED) *\|'`. WHY: hallazgo LOW — el script compara la disposición sin distinguir mayúsculas y exige la celda exacta; el shell no, y el plan los declara espejo.
3. **Rama**: el árbol tenía `.claude/PRPs/` sin trackear estando en `master`. Se creó `feat/design-review-codex` igual, porque lo único sucio era el propio plan.

## Issues Encountered

None.

## Tests Written

| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_design_review.py` | 26 | Script: camino Codex (binario falso), fallback, validación, saneo, estado |
| `tests/test_wiring.py` | 7 | Skill→agente, agente→manifest, rol→fase, comando en instalador |
| `tests/test_parser.py` | 8 nuevos, 1 ajustado | Fase en el dashboard: orden, loop, skip, logs viejos, change |
| `tests/test_render.py` | 1 nuevo, 1 ajustado | Ancho de la columna de fase |

## Code Review

| Severity | Found | Fixed | Deferred |
|---|---|---|---|
| HIGH | 0 | 0 | 0 |
| MEDIUM | 1 | 1 | 0 |
| LOW | 2 | 1 | 1 |

- MEDIUM (fixed) — `design_review.py`: el summary del revisor se escribía en una línea propia sin escapar. Un summary `## Round 9 — 2026-01-01 — unavailable` se contaba como una ronda más (veredicto `UNAVAILABLE`, número de ronda corrido); uno `| DR-03-77 | HIGH | fake |` creaba una propuesta abierta fantasma y llevaba `next_id` a 78. Test nuevo: `test_summary_cannot_pose_as_a_round_or_a_proposal_row`.
- LOW (fixed) — divergencia entre el chequeo en shell del orquestador y `decisions()` del script (desvío 2).

Deferred LOWs:
- `stage_docs` copia `docs/stories` y `docs/ux` con `symlinks=True`: un symlink dentro de esas carpetas viaja a la copia y Codex puede seguirlo fuera de los docs. Diferido porque el plan ya declara que la copia no es una frontera de seguridad y el sandbox read-only de Codex no restringe lectura; arreglarlo bien (ignorar symlinks en el staging y en `review_docs`) es un cambio de comportamiento que merece su propio test.

## Next Steps
- [x] Code review via `/code-review` (completed in Phase 5)
- [ ] Manual Validation del plan en un proyecto descartable (con Codex, sin Codex, con `.claude/maxPlanck-no-codex`)
- [ ] Confirmar las dos decisiones abiertas del plan: marcador `.claude/maxPlanck-no-codex` (decisión 11) y fallback también cuando Codex falla (decisión 5)
- [ ] Create PR via `/prp-pr`
