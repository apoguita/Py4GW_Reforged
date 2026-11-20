# PACK COMPLET : Work Branch réintégrée sur la base du main Apo

> Pack de test, **non validé en jeu**. La compilation Python statique ne garantit pas la compatibilité Py4GW.

## Méthode
- Socle : ZIP main Apo (16 octobre 2026).
- Scripts, donjons, builds et ajouts exclusifs Work Branch issus de la première passe.
- Groupe des 7 services BottingTree repris à l’étape 2.
- Modules complémentaires réintégrés sur la base d’Apo : voir inventaire ci-dessous.
- `Item.py` et `behaviourtrees_src/movement.py` restent sur la version d’Apo afin de ne pas réintroduire le crash MerchantRules / contournement défectueux. Cette conservation peut impliquer des fonctionnalités à retester.

## Analyse statique
- Fichiers Python analysés : **1780**
- Erreurs de syntaxe : **1** (fichier hérité `Examples and tests/Legacy code and tests/Misc/results_log.py`, identique à la source étape 2 : c’est un extrait de données, pas un script Python fonctionnel)
- Symboles de services attendus manquants : **aucun**
- Fichiers présents dans Work absents du pack : **0**

## Intégration CoreLib et MerchantRules
- `Py4GWCoreLib/BottingTree.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/FrameTree/frame.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/FrameTree/frame_aliases.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/FrameTree/frame_ids.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/FrameTree/frame_registry.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/HeroAI/combat.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/HeroAI/custom_skill_src/ranger.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/HeroAI/resurrection_scroll.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/HeroAI/ui.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/HeroAI/ui_base.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/Item.py` : Apo conservé (revue en jeu)
- `Py4GWCoreLib/botting_src/event.py` : Work intégré, adaptation à tester
- `Py4GWCoreLib/botting_src/helpers_src/Multibox.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/botting_src/subclases_src/EVENTS_src.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/botting_src/subclases_src/MULTIBOX_src.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/botting_tree_src/config.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/botting_tree_src/enums.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/botting_tree_src/planner.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/botting_tree_src/services.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/botting_tree_src/ticks.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/botting_tree_src/upkeep.py` : étape 2 déjà intégrée
- `Py4GWCoreLib/enums_src/Multiboxing_enums.py` : ajouts Work intégrés sur Apo
- `Py4GWCoreLib/py4gwcorelib_src/system_settings/loot_filters/__init__.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/routines_src/behaviourtrees_src/items.py` : Work intégré, changements non additifs
- `Py4GWCoreLib/routines_src/behaviourtrees_src/movement.py` : Apo conservé (revue en jeu)
- `Py4GWCoreLib/routines_src/behaviourtrees_src/shared.py` : ajouts Work intégrés sur Apo
- `Sources/icefox/MerchantRules/profiles.py` : source manquante

## Exceptions et limites
- L’évitement d’obstacle **n’a pas été restauré** : une passe dédiée est nécessaire, conformément à ta demande.
- `Item.py` conserve Apo ; les changements de noms runtime d’items et MerchantRules devront être testés en jeu.
- Les fichiers HeroAI et interface contenant de nombreuses différences sont reportés de Work ; validation fonctionnelle nécessaire.
- Les changements du cœur BottingTree à l’étape 2 proviennent de Work, sans garantie que toutes les fonctions historiques d’Apo aient été conservées.
- Pas de test dynamique en jeu, de compilation Py4GW native, ni de push GitHub.
- Ne pas publier ou remplacer la branche active avant validation des donjons, du rez multibox, restock et MerchantRules.

## Échecs de parsing
- `Examples and tests/Legacy code and tests/Misc/results_log.py` : unexpected indent (results_log.py, line 1)
