# Protocole scientifique minimal

## Reproductibilité

Toute expérience doit enregistrer :

- version Git ;
- seed ;
- configuration complète ;
- nombre de ticks ;
- contexte d'exécution non canonique ;
- tick/digest du snapshot source si l'expérience dérive du monde canonique ;
- digest initial et final.

Une expérience n'est jamais un « mode » du monde canonique. Elle s'exécute sur une copie/fork explicitement non canonique qui ne doit pas pouvoir écrire dans la persistance officielle.

## Interprétation

Un comportement observé dans un seed n'est pas considéré comme un phénomène émergent général. Il doit être reproduit sur plusieurs seeds et comparé à une condition contrôle.

## Baseline V0.1

La baseline par défaut vise un turnover écologique sans croissance exponentielle immédiate : nourriture limitée, reproduction faible mais non nulle, vieillissement et mortalité actifs.

Les paramètres ne sont pas présentés comme biologiquement réalistes. Ils constituent un environnement expérimental artificiel cohérent et mesurable.

## Tests futurs d'émergence

Pour un comportement candidat :

1. mesurer sa fréquence ;
2. identifier les individus concernés ;
3. comparer aux comportements aléatoires attendus ;
4. tester sa persistance temporelle ;
5. tester sa propagation entre individus ;
6. reproduire sur plusieurs seeds ;
7. seulement ensuite le qualifier d'apprentissage/culture potentielle.

Toute intervention humaine ou divine est enregistrée comme facteur expérimental.

## LLM

Le LLM ne doit jamais être utilisé comme preuve d'un phénomène. Il peut proposer une hypothèse, mais les métriques du moteur doivent la tester.
