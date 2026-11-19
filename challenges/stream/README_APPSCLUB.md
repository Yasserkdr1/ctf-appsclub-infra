# Stream — AppsClub (Web / N0blair)

Intégration basée sur `challenge1.zip` (source de l'auteur) et sur le scénario
`vibechain-breach` de notre dépôt AppsClub.

## Contenu

- `app/`: PHP Apache, SQLite et fichiers de l'épreuve ; SQLi intentionnelle inchangée.
- `pulumi/`: SDK Chall-Manager v0.6.6, port applicatif 8080, NodePort dynamique,
  IP worker `10.60.2.10`, accès gateway `10.60.1.10/32`, contrôle réseau VIP.
- Flag original conservé, suffixe hexadécimal déterministe par identité d'instance,
  dans la variable `FLAG` injectée dans le conteneur et dans la sortie Pulumi.
- Hardened: UID/GID 10001, rootfs read-only, capacités supprimées, /tmp emptyDir,
  aucun jeton Kubernetes monté, seccomp RuntimeDefault.

## Installation du répertoire

Copier `appsclub-stream` dans :

`~/ctf/ctf-appsclub-infra/challenges/stream`

## 1. Tester l'app localement (sur WSL avec Docker)

```sh
cd ~/ctf/ctf-appsclub-infra/challenges/stream/app
docker compose up --build -d
curl -fsSI http://127.0.0.1:8088/
curl -fsS http://127.0.0.1:8088/search.php | grep -F 'Search for a movie'
docker compose logs --tail=30
docker compose down
```

En local le flag est fictif, pas le flag du concours.

## 2. Publier l'image applicative GHCR

Authentification préalable à GHCR via les identifiants Docker déjà configurés :

```sh
cd ~/ctf/ctf-appsclub-infra/challenges/stream
docker build --platform linux/amd64 -t ghcr.io/yasserkdr1/ctf-stream:v0.1.0 ./app
docker push ghcr.io/yasserkdr1/ctf-stream:v0.1.0
```

GHCR privé : vérifier `ghcr-readonly` et l'imagePullSecret de la ServiceAccount
par défaut dans le namespace `cm-target-daunsoix`.

## 3. Compiler et publier le scénario Pulumi en OCI

```sh
cd ~/ctf/ctf-appsclub-infra/challenges/stream/pulumi
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o ctf-stream .
ORAS_BIN="$(command -v oras || echo "$(go env GOPATH)/bin/oras")"
"$ORAS_BIN" push --artifact-type application/vnd.ctfer-io.scenario \
  ghcr.io/yasserkdr1/ctf-stream-scenario:v0.1.0 \
  Pulumi.yaml:application/vnd.ctfer-io.file \
  ctf-stream:application/vnd.ctfer-io.file
```

L'auth ORAS vers GHCR doit être déjà configurée. Si nécessaire, la réutiliser
sans afficher de token sur le terminal ou dans le dépôt.

## 4. Configurer le challenge CTFd

- Nom : `Stream`; catégorie : `Web`; auteur : `N0blair`.
- Description : `Netflix`.
- Valeur initiale : 500 ; decay : 450 ; minimum : 100.
- État : **Hidden** pour les tests.
- Type de challenge : **Chall-Manager** (comme VibeChain/Loopback),
  URI de scénario : `ghcr.io/yasserkdr1/ctf-stream-scenario:v0.1.0`.
- Ne PAS enregistrer de flag statique supplémentaire : celui de Chall-Manager
  est injecté et validé par instance.

## 5. Vérifications d'instance

Après la première création d'instance dans CTFd :

```sh
ssh ctf-worker 'sudo k3s kubectl -n cm-target-daunsoix get pods,svc'
ssh ctf-gateway 'sudo systemctl status appsclub-vip-sync.timer --no-pager'
```

Contrôler : image privée récupérée, Pod Running, port **8080**, VIP privée
dans la page CTFd (jamais de NodePort direct), réponse de la page Web via
WireGuard, flag conforme, deux équipes avec flags/VIP différents, isolation.
Le flag ne doit pas être exposé dans les logs publics ni collé en chat.

## Notes

- Ne pas changer les versions ni tags d'images déjà utilisées par les défis existants.
- La nouvelle image et le scénario sont deux packages distincts dans GHCR.
- Le ZIP source contient un flag non personnalisé dans challenge.yaml et
  docker-compose.yml : ne pas distribuer ce ZIP original aux joueurs.
- La sécurité du flag unique dépend de la confidentialité du scénario OCI ;
  ne pas publier les sources Pulumi contenant `baseFlag` en public.
- Le port 8088 est seulement pour le test `docker compose` sur WSL.
