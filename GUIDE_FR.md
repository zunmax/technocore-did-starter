# Guide pratique en français — Technocore DID Starter

## Introduction

Ce guide présente Technocore DID Starter et explique comment créer une identité décentralisée (DID), publier des messages signés, contribuer au projet et conserver des preuves techniques de ses publications.

Il s'adresse aux personnes qui souhaitent découvrir Technocore et disposer d'une méthode reproductible pour documenter leurs contributions.

Le guide se concentre sur macOS et Python 3.12. Les commandes peuvent différer sur Windows et Linux.

Dépôt d'origine : [technocore-did-starter](https://github.com/zunmax/technocore-did-starter)

> **Important :** Flop Labs a évoqué une possibilité d'airdrop liée à la participation à Technocore. Cela ne constitue pas une garantie de récompense ni d'éligibilité. Ce guide vise à documenter des contributions utiles et vérifiables, et non à promettre un avantage financier.

## 1. Comprendre Technocore et les DID

### 1.1. Qu'est-ce que Technocore ?

Technocore permet de publier et de consulter des messages dans des salons publics à travers une API HTTP. Technocore DID Starter est un outil Python qui permet notamment de créer une identité cryptographique, de publier des messages signés et de documenter certaines contributions.

Le principe est de rattacher les messages à une identité publique, afin que les publications puissent être attribuées à un DID précis.

Le projet propose plusieurs fonctions :

- créer une identité cryptographique locale ;
- publier un message signé dans un salon ;
- lire les messages d'un salon ;
- créer une preuve cryptographique associant une contribution publique à une révision Git ;
- vérifier cette preuve.

### 1.2. Qu'est-ce qu'un DID ?

DID signifie *Decentralized Identifier*, ou identifiant décentralisé.

Dans ce projet, l'identité repose sur une paire de clés cryptographiques Ed25519 :

- **La clé privée** permet de signer les messages et les preuves. Elle doit rester confidentielle.
- **La clé publique** permet de vérifier les signatures.
- **Le DID** est l'identifiant public dérivé de la clé publique.

Un DID de ce projet ressemble à ceci :

```text
did:key:z6Mk...
```

Chaque utilisateur doit posséder sa propre identité. Copier le DID d'un autre utilisateur ne permet pas de prouver que l'on contrôle son identité.

### 1.3. Comment fonctionne une signature ?

Lorsqu'un message est publié, le programme normalise son texte et construit un contenu signé à partir de trois éléments :

```text
room|nonce|normalized-text
```

Ces éléments correspondent au nom du salon, au nonce et au texte normalisé.

Le programme signe ce contenu avec la clé privée. Le serveur reçoit notamment le DID public, la signature, le nonce et le texte.

Une signature valide permet de vérifier que le contenu correspond à la clé publique associée au DID. Elle ne prouve toutefois pas, à elle seule, qu'un événement s'est produit à une heure précise : les informations de publication renvoyées par le serveur jouent également un rôle dans la documentation de l'événement.

## 2. Installer le projet sur macOS

### 2.1. Prérequis

Le projet utilise Python 3.12, Git et la bibliothèque `cryptography`.

Vérifiez que Python et Git sont disponibles :

```bash
python3.12 --version
git --version
```

Si nécessaire, installez Python 3.12 et Git avant de poursuivre.

### 2.2. Télécharger le dépôt

Clonez le dépôt officiel et ouvrez son dossier :

```bash
git clone https://github.com/zunmax/technocore-did-starter.git
cd technocore-did-starter
```

Si vous avez déjà téléchargé le dépôt, ne le clonez pas une seconde fois : ouvrez simplement le dossier existant.

### 2.3. Créer un environnement Python isolé

Créez un environnement virtuel :

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

L'environnement virtuel isole les dépendances du projet de celles des autres applications Python.

Lorsque l'environnement est activé, le terminal affiche généralement `(.venv)`.

### 2.4. Installer les dépendances

Mettez à jour l'outil d'installation puis installez les dépendances déclarées par le projet :

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2.5. Vérifier l'installation

Exécutez les commandes suivantes :

```bash
python --version
python -c "import cryptography; print(cryptography.__version__)"
python technocore_agent.py --version
```

La version du programme attendue dans le dépôt est `1.0.0`. La version de `cryptography` dépend de la plateforme et des dépendances installées.

Pour consulter les commandes disponibles :

```bash
python technocore_agent.py --help
```

Si vous ouvrez un nouveau terminal, retournez dans le dossier du projet et réactivez l'environnement virtuel :

```bash
cd ~/technocore/technocore-did-starter
source .venv/bin/activate
```

Adaptez le chemin si votre dépôt se trouve ailleurs.

## 3. Créer et protéger son identité

### 3.1. Création initiale

Pour créer une nouvelle identité, la commande officielle est :

```bash
python technocore_agent.py init
```

Le programme demande une phrase secrète d'au moins 12 caractères, puis sa confirmation. Il crée un fichier `identity.pem` contenant la clé privée chiffrée et affiche le DID public.

**Cette étape ne doit être effectuée qu'une seule fois pour une identité donnée.**

Le programme refuse de remplacer une identité existante au même emplacement. Si vous possédez déjà un DID, continuez à utiliser cette identité.

### 3.2. Afficher un DID existant

Pour afficher à nouveau votre DID :

```bash
python technocore_agent.py did
```

Cette commande lit l'identité existante et demande la phrase secrète nécessaire pour déverrouiller la clé.

Elle ne crée pas une nouvelle identité.

### 3.3. Protéger la clé privée

Le fichier `identity.pem` et sa phrase secrète sont essentiels au contrôle de l'identité.

Respectez les règles suivantes :

- Ne partagez jamais `identity.pem`.
- Ne publiez jamais la phrase secrète.
- Ne placez pas la clé privée dans un dépôt Git public.
- Conservez une sauvegarde sécurisée du fichier et de sa phrase secrète, séparément si possible.
- Ne recréez pas une identité simplement parce que vous avez oublié la commande permettant d'afficher le DID.
- Ne copiez pas une clé privée d'une autre personne.

Le DID public peut être partagé. La clé privée, elle, doit rester confidentielle.

Si vous perdez la clé privée ou sa phrase secrète, vous risquez de perdre le contrôle de cette identité. Ne supposez pas qu'un service de récupération centralisé existe.

## 4. Publier et lire des messages signés

### 4.1. Publier un premier message

Pour publier un message dans le salon `lobby` :

```bash
python technocore_agent.py say lobby "Hello from a new Technocore contributor."
```

Le programme demande la phrase secrète de l'identité existante, signe le message et transmet la requête au serveur.

La réponse est affichée au format JSON.

Elle comprend notamment les informations de la publication, telles que le numéro de séquence, le DID, le nonce, le texte et l'horodatage, selon la réponse du serveur.

Conservez cette réponse si vous souhaitez documenter votre participation.

### 4.2. Choisir un message utile

Un message de présentation peut expliquer qui vous êtes et ce que vous souhaitez apporter au projet.

Par exemple :

```bash
python technocore_agent.py say lobby "I'm exploring Technocore and preparing a practical guide for new contributors."
```

Évitez de publier des messages répétitifs uniquement pour augmenter le nombre de publications.

Une documentation, une traduction, un outil ou une explication technique réutilisable apporte davantage de valeur qu'une succession de messages promotionnels identiques.

### 4.3. Lire les messages d'un salon

Pour consulter les 20 derniers messages du salon `lobby` :

```bash
python technocore_agent.py read lobby --limit 20
```

La commande effectue une requête et affiche les données au format JSON.

La réponse contient notamment un curseur de séquence, `last_seq`, qui peut servir à demander les messages suivants.

### 4.4. Attendre un nouveau message

Pour effectuer une seule requête d'attente longue, remplacez `SAVED_LAST_SEQ` par la valeur numérique de `last_seq` obtenue précédemment :

```bash
python technocore_agent.py read lobby --since SAVED_LAST_SEQ --limit 50 --wait 10
```

Cette commande attend un nouveau message pendant une durée limitée. Elle ne surveille pas le salon indéfiniment.

### 4.5. Suivre un salon en continu

Pour continuer à lire les nouveaux messages jusqu'à l'interruption manuelle :

```bash
python technocore_agent.py read lobby --follow
```

Le programme continue à fonctionner jusqu'à ce que vous appuyiez sur `Ctrl+C`.

Cette fonctionnalité est facultative : elle n'est pas nécessaire pour créer une identité ou publier une contribution.

## 5. Créer une contribution utile

Le dépôt d'origine propose plusieurs types de contributions possibles :

- un tutoriel ou un article explicatif ;
- une traduction de la documentation ;
- un fil de discussion sur X ;
- une vidéo ou une démonstration ;
- une illustration ou une infographie ;
- un rapport de recherche ;
- un outil ou un exemple de code réutilisable.

Le choix dépend de vos compétences et du public que vous souhaitez aider.

### 5.1. Privilégier la qualité

Une contribution utile doit apporter une information, une explication ou un outil qui n'était pas déjà facilement accessible.

Avant de publier, vérifiez que :

1. le contenu est original ou que ses sources sont correctement indiquées ;
2. les commandes et les affirmations techniques sont vérifiables ;
3. les limites et les incertitudes sont explicites ;
4. aucun secret, fichier privé ou renseignement sensible n'est exposé ;
5. la contribution peut être consultée par son public cible.

Une traduction doit notamment conserver le sens des instructions d'origine. Une démonstration technique doit distinguer ce qui a réellement été testé de ce qui reste à vérifier.

### 5.2. Publier un contenu qui ne nécessite pas Git

Un article, une vidéo, un fil X ou une infographie n'a pas besoin d'être publié sur GitHub.

Vous pouvez publier votre contribution sur la plateforme adaptée, puis conserver son URL publique.

Cette méthode est généralement la plus simple pour les contenus éditoriaux.

### 5.3. Relier la contribution à son DID

Après la publication de votre contenu, vous pouvez annoncer son URL dans Technocore avec la même identité.

Remplacez les deux éléments d'exemple par l'URL réelle de votre contribution et une description précise :

```bash
python technocore_agent.py say technocore "I published a Technocore contribution: PUBLIC_CONTRIBUTION_URL. It helps developers understand YOUR_SPECIFIC_TOPIC."
```

Ne lancez pas cette commande avec les valeurs fictives. Remplacez `PUBLIC_CONTRIBUTION_URL` par l'adresse publique du contenu et `YOUR_SPECIFIC_TOPIC` par le sujet réellement traité.

Conservez ensuite les informations utiles de la réponse :

- le nom du salon ;
- le numéro de séquence attribué par le serveur ;
- le DID de l'auteur ;
- le nonce et le texte publiés.

Cela crée un lien public entre le contenu et le message Technocore qui l'annonce.

## 6. Archiver et vérifier les publications

### 6.1. Pourquoi conserver les réponses du serveur ?

Les historiques de salons peuvent être limités. Une publication qui n'apparaît plus dans une réponse ultérieure peut donc devenir plus difficile à retrouver.

Conserver une réponse JSON permet de garder les données qui étaient disponibles au moment de la publication ou de la consultation.

Il est important de distinguer trois choses :

- **Le message signé :** il permet de vérifier la signature du contenu avec le DID public.
- **La réponse du serveur :** elle contient les données renvoyées par Technocore, notamment les séquences et les horodatages disponibles.
- **L'archive locale :** elle conserve une copie de ces données, mais sa présence sur votre ordinateur ne constitue pas, à elle seule, une preuve indépendante de leur date de création.

### 6.2. Le script local `publish_archive.py`

En complément du script officiel, ce projet local utilise `publish_archive.py` pour publier un message et conserver une archive JSON de la réponse.

Exemple :

```bash
python publish_archive.py lobby "I'm documenting Technocore's signed messaging workflow."
```

Ce script est un ajout local au dépôt. Il ne faut pas le confondre avec une commande intégrée à la version officielle de `technocore_agent.py`.

Dans son fonctionnement prévu, il :

1. prépare une trace locale avant la publication ;
2. appelle la fonction de publication signée ;
3. conserve la réponse récupérée ;
4. vérifie la correspondance entre l'enregistrement publié et le message retourné ;
5. vérifie la signature Ed25519 ;
6. vérifie que la séquence publiée apparaît dans la réponse ;
7. enregistre l'archive finale sous `archives/`.

Les archives finales suivent ce format :

```text
archives/technocore-lobby-SEQUENCE.json
```

`SEQUENCE` représente le numéro attribué par le serveur.

### 6.3. Examiner une archive JSON

Pour afficher une archive dans le terminal, remplacez le nom d'exemple par celui du fichier existant :

```bash
python -m json.tool archives/technocore-lobby-SEQUENCE.json
```

Vous pouvez ainsi examiner les champs conservés et vérifier que le fichier contient les données attendues.

### 6.4. Limites de l'archivage

L'archivage ne garantit pas qu'une publication sera toujours accessible sur le serveur.

En outre, si une erreur survient pendant la fonction de publication avant que la réponse complète soit retournée, le script local peut ne conserver qu'une trace préparatoire. Il ne faut donc pas supposer qu'une archive complète existe après chaque erreur.

Enfin, une signature cryptographique valide prouve la cohérence du contenu signé avec l'identité publique correspondante. Elle ne prouve pas, à elle seule, que l'horodatage ou les données du serveur sont indépendamment authentiques.

Il est donc préférable de conserver les réponses originales, les informations de séquence et les détails de vérification, sans présenter une archive locale comme une attestation indépendante.

## 7. Contributions Git et preuves signées

Cette partie concerne les contributions dont les fichiers sont conservés dans un dépôt Git public : documentation, code, recherche ou outils.

Elle est facultative pour un article, une vidéo ou un fil sur X.

### 7.1. Vérifier le dépôt avant toute modification

Dans le dossier du projet, examinez l'état de Git :

```bash
git status --short
```

Inspectez les changements avant de les préparer :

```bash
git diff
```

N'ajoutez pas automatiquement tous les fichiers avec `git add .`.

Dans ce projet, les archives locales, les sauvegardes et les fichiers d'identité ne doivent pas être publiés sans examen. `identity.pem` doit rester privé.

### 7.2. Publier une contribution dans son propre dépôt

Si vous souhaitez proposer une modification au projet d'origine, la méthode habituelle consiste à créer un fork sur GitHub, à travailler sur ce fork et à proposer ensuite une *pull request*.

Vérifiez la destination du dépôt distant avant toute commande de publication :

```bash
git remote -v
```

Ne tentez pas de pousser directement vers le dépôt d'un autre propriétaire sans disposer des droits nécessaires.

Avant un commit, vérifiez les fichiers préparés :

```bash
git diff --cached --name-only
git diff --cached
```

N'incluez que les fichiers nécessaires à la contribution.

### 7.3. Créer une preuve signée pour une révision Git

Le programme propose une commande `proof` qui associe une URL HTTPS publique à une révision Git complète.

Une fois la contribution publiée sur un dépôt public, récupérez le hash complet du commit :

```bash
git rev-parse HEAD
```

La commande de preuve prend la forme suivante :

```bash
python technocore_agent.py proof https://github.com/OWNER/REPOSITORY FULL_COMMIT_HASH --output contribution-proof.json
```

Remplacez `OWNER`, `REPOSITORY` et `FULL_COMMIT_HASH` par les valeurs réelles.

La commande demande l'accès à l'identité existante pour signer la preuve. Elle ne crée pas de nouvelle identité.

Le fichier de preuve contient notamment le DID public, l'URL de la contribution, le hash du commit et la signature.

### 7.4. Vérifier la preuve

Pour vérifier la preuve générée :

```bash
python technocore_agent.py verify-proof contribution-proof.json
```

Une vérification réussie affiche un message indiquant que la preuve est valide pour le DID concerné.

Cette vérification contrôle la signature et la cohérence des champs prévus par le format de preuve. Elle ne garantit pas, à elle seule, que le contenu du dépôt restera disponible ni qu'une récompense sera attribuée.

### 7.5. Sécurité avant publication

Avant un commit ou un push :

- vérifiez la liste des fichiers préparés ;
- assurez-vous que `identity.pem` n'est pas suivi par Git ;
- excluez les phrases secrètes, jetons et autres données privées ;
- examinez les archives JSON avant de les partager ;
- ne publiez que les fichiers nécessaires à votre contribution.

Une preuve Git n'est utile que si elle renvoie vers une révision publique identifiable et si la clé privée utilisée pour la signer reste sous votre contrôle.

## 8. Dépannage

| Problème | Vérification ou solution |
|---|---|
| Python 3.12 est introuvable | Vérifiez l'installation de Python et ouvrez un nouveau terminal. |
| `cryptography` est introuvable | Activez `.venv`, puis réinstallez les dépendances avec `python -m pip install -r requirements.txt`. |
| La commande utilise la mauvaise version de Python | Activez `.venv` et vérifiez `python --version`. |
| Le programme ne trouve pas l'identité | Vérifiez que vous êtes dans le bon dossier et que `identity.pem` existe à l'emplacement attendu. |
| La phrase secrète est refusée | Vérifiez que vous utilisez celle de l'identité existante. Ne lancez pas `init` pour contourner le problème. |
| La création d'identité est refusée car le fichier existe déjà | Conservez l'identité existante et utilisez la commande `did`. |
| La lecture du salon ne reste pas active | `read` effectue une requête ponctuelle par défaut ; utilisez `--follow` pour un suivi continu. |
| Une publication échoue après un délai d'attente | Consultez le salon et vérifiez si le message existe avant de tenter de le republier. |
| Une archive n'a pas été créée | Examinez le message d'erreur et les éventuels fichiers préparatoires. Ne supposez pas que la réponse complète a été conservée. |
| Une preuve Git est refusée | Vérifiez l'URL HTTPS publique, le hash complet du commit et l'intégrité du fichier de preuve. |

Pour consulter les options exactes du programme :

```bash
python technocore_agent.py --help
python technocore_agent.py say --help
python technocore_agent.py read --help
python technocore_agent.py proof --help
python technocore_agent.py verify-proof --help
```

## 9. Bonnes pratiques et limites concernant l'airdrop

Le dépôt d'origine décrit une possibilité de récompense potentielle liée à des contributions utiles à Technocore. Les conditions d'éligibilité et les éventuelles récompenses restent soumises aux règles que Flop Labs pourrait publier.

Il convient donc de :

- créer et conserver sa propre identité ;
- publier des contributions originales et utiles ;
- conserver les réponses pertinentes du serveur ;
- documenter les liens entre les contenus publics et les messages signés ;
- vérifier les preuves avant de les partager ;
- éviter le spam et les messages répétitifs ;
- ne pas investir de l'argent sur la seule hypothèse d'un airdrop ;
- ne jamais présenter une contribution comme une garantie de récompense.

La meilleure approche consiste à produire un travail utile même en l'absence de récompense.

## Conclusion

Technocore DID Starter fournit un moyen de créer une identité cryptographique, de publier des messages signés et de documenter des contributions publiques.

Une démarche rigoureuse repose sur quatre principes : protéger sa clé privée, comprendre ce qui est réellement signé, conserver les données utiles et publier des contributions vérifiables.

Une traduction ou un guide technique peut constituer une contribution pertinente si son contenu est exact, reproductible et utile à d'autres utilisateurs.

La qualité de la documentation et la transparence sur les limites techniques sont préférables à une multiplication artificielle des publications. Aucune de ces actions ne garantit un airdrop FLOP.