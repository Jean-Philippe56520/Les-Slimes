# Protocole scientifique minimal

## Reproductibilité

Toute expérience dérivée du monde canonique doit enregistrer au minimum :

- commit Git source ;
- configuration complète source ;
- tick source ;
- séquence d'événements source ;
- digest source ;
- identifiant d'expérience et de run ;
- condition expérimentale ;
- seed expérimental si le RNG est explicitement reseedé ;
- digest initial ;
- nombre de ticks exécutés ;
- digest final ;
- contexte d'exécution non canonique.

Une expérience n'est jamais un « mode » du monde canonique. Elle s'exécute sur une copie/fork explicitement non canonique qui ne doit pas pouvoir écrire dans la persistance officielle.

## Fork canonique

Un fork scientifique dérivé du monde officiel suit ces règles :

1. le snapshot source est lu de manière cohérente et sans écriture sur la base canonique ;
2. le `World` est reconstruit dans une nouvelle base explicitement `non_canonical_experiment` ;
3. command queue, writer lease et acteurs runtime canoniques ne sont pas recopiés ;
4. le runtime canonique refuse une base expérimentale ;
5. le runner expérimental refuse une base canonique ;
6. sans reseed ni intervention, le digest initial du fork est identique au digest source ;
7. toute modification expérimentale volontaire doit être traitée comme facteur expérimental et documentée.

## Seeds

Le `config.seed` appartient à l'histoire d'origine du monde et n'est pas remplacé silencieusement lors d'un fork.

Un éventuel `experiment_seed` correspond à un reseed explicite du RNG après clonage. Le manifeste doit indiquer `rng_reseeded=true` et conserver séparément le seed historique de la configuration source.

Pour comparer contrôle et traitement, utiliser autant que possible les mêmes seeds expérimentaux par paire.

## Interprétation

Un comportement observé dans un seed n'est pas considéré comme un phénomène émergent général. Il doit être reproduit sur plusieurs seeds et comparé à une condition contrôle.

Toujours distinguer :
- observation ;
- corrélation ;
- hypothèse ;
- résultat reproduit ;
- conclusion.

## Baseline V0.1

La baseline par défaut vise un turnover écologique sans croissance exponentielle immédiate : nourriture limitée, reproduction faible mais non nulle, vieillissement et mortalité actifs.

Les paramètres ne sont pas présentés comme biologiquement réalistes. Ils constituent un environnement expérimental artificiel cohérent et mesurable.

## Tests d'émergence

Pour un comportement candidat :

1. mesurer sa fréquence ;
2. identifier les individus concernés ;
3. comparer aux comportements aléatoires attendus ;
4. tester sa persistance temporelle ;
5. tester sa propagation entre individus ;
6. reproduire sur plusieurs seeds ;
7. comparer à une condition contrôle ;
8. seulement ensuite le qualifier d'apprentissage/culture potentielle.

Toute intervention humaine ou divine est enregistrée comme facteur expérimental.

## LLM

Le LLM ne doit jamais être utilisé comme preuve d'un phénomène. Il peut proposer une hypothèse, mais les métriques du moteur doivent la tester.
