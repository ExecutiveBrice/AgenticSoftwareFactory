# Crew System Review

CREW SYSTEM VALIDATED

## Architecture finale

Le framework fournit un socle Pydantic strict, un service d'artefacts borné au repository, un générateur d'identifiants local, un registre de crews, des ressources YAML validées, et un Flow MVP persistant dans `.factory/state/`.

## Crews et agents

- discovery: repository_analyst, business_analyst, requirements_reviewer, discovery_writer.
- knowledge: project_librarian, documentation_auditor.
- design: solution_architect, domain_designer, ux_designer, security_architect, design_reviewer.
- planning: delivery_planner, technical_task_writer, test_planner, dependency_reviewer.
- development: codebase_analyst, software_developer, test_developer, documentation_developer, implementation_reviewer.
- qa: qa_analyst, test_executor, regression_analyst, qa_reporter.
- review: code_reviewer, architecture_reviewer, security_reviewer, release_reviewer, review_lead.

## Tasks par crew

Chaque crew possède un `agents.yaml` et un `tasks.yaml` sous `src/ai_software_factory/resources/crews/<crew>/`. Les tâches référencent des agents existants et restent génériques, sans métier, langage ou framework cible codé en dur.

## Matrice des permissions

| Crew | Lecture | Création | Modification | Jamais toucher |
| --- | --- | --- | --- | --- |
| Discovery | repository, docs, project | `project/discovery/`, `project/specifications/` | artefacts discovery/spec seulement | code source cible |
| Knowledge | artefacts validés | `project/decisions/`, `project/reviews/` | `project/context.md`, `project/glossary.md`, `project/roadmap.md`, `project/changelog.md` | code source cible |
| Design | specs, architecture, décisions, code concerné | `project/architecture/FEAT-*` | design drafts | code source cible |
| Planning | specs/design approuvés, backlog | `project/backlog/FEAT-*` | backlog de la feature | code source cible |
| Development | task approuvée, code concerné | code/tests/docs nécessaires, manifestes | périmètre de task uniquement | hors repository, hors périmètre |
| QA | task, diff, tests, manifestes | `project/reviews/QA-*` | rapports QA | code source cible |
| Review | QA passed, diff, design | `project/reviews/TECH-*` | rapports review | code source cible |

## Graphe de routage

Discovery démarre une demande, peut suspendre pour clarification, puis attend l'approbation de spécification. Les approbations mènent à Knowledge, Design, Planning, Development, QA, Review, Knowledge et acceptation finale. Les verdicts QA et Review sont routés explicitement par `flows.routing`.

## Couverture de tests

Les tests couvrent les modèles, verdicts, identifiants, protection path traversal, absence d'écrasement, registre, ressources YAML, persistance atomique et routage principal.

## Limites connues

- Les crews sont testables et configurées mais n'exécutent pas CrewAI.
- Les productions documentaires sont des abstractions MVP.
- Les commandes CLI de validation enregistrent une intention MVP et ne déclenchent pas encore toute l'orchestration.

## Fonctionnalités non implémentées

- Appels LLM réels.
- Adaptateurs CrewAI complets.
- Analyse exhaustive de repositories cible.
- Édition autonome de code par Development Crew.

## Recommandation pour l'intégration des premiers LLM

Ajouter un port d'adaptateur LLM injecté dans `BaseCrew`, conserver les tests avec fake adapter, limiter les sorties à des modèles Pydantic validés, et activer d'abord Discovery puis QA en lecture seule.
