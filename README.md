# TP Cassandra : cluster 3 nœuds, réplication et pannes (OMDb)

## Sujet

Déployer un cluster Cassandra de 3 nœuds avec Docker, y charger des films
de l'API de la veille (j'ai utilisé celle d'OMDb) avec un facteur de réplication de 3, tester les niveaux de
cohérence (ONE, QUORUM et ALL) et observer la tolérance à la panne d'un nœud (fait sur cass3).

## Données

100 films OMDb (mots-clés `batman`, `star`, `love`, `war`, `night`).
Champs : `imdbID`, `Title`, `Year`, `Runtime`, `Genre`, `Director`,
`Country`, `imdbRating`, `imdbVotes`.

## Lancer le projet

```bash
docker compose up -d cass1 cass2        # attendre 2 nœuds UN
docker compose up -d cass3
docker exec cass1 nodetool status       # 3 nœuds UN

docker exec -i cass1 cqlsh < queries/10_cluster_schema.sql

python -m venv venv
source venv/Scripts/activate            # Linux/macOS : venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # renseigner OMDB_API_KEY
python script/import_movies.py
```

## Scénarios testés

| Fichier | Contenu |
|---|---|
| `queries/10_cluster_schema.sql` | keyspace `movies_cluster` (RF = 3) et table `movies` |
| `queries/11_consistency.sql` | lectures en ONE, QUORUM, ALL |
| `queries/12_panne.sql` | panne de `cass3` : lecture ALL en échec, écriture QUORUM réussie |

Analyse détaillée : [documentation/cluster.md](documentation/cluster.md).

## Résultats principaux

- `getendpoints` renvoie 3 IP : chaque film est répliqué sur les 3 nœuds.
- `cass3` arrêté : lecture `ALL` impossible (`UnavailableException`),
  écriture `QUORUM` possible.
- `cass3` redémarré : il retrouve le film écrit pendant la panne.

## Structure

```text
README.md
docker-compose.yml
requirements.txt
.env.example
script/        getapi.py (client OMDb), import_movies.py (import cluster)
queries/       10_cluster_schema, 11_consistency, 12_panne
documentation/ cluster.md
captures/      captures d'écran
```
## Captures

### Cluster de 3 nœuds
![nodetool status](captures/C1_nodetool_3_noeuds.png)

### Import des 100 films (RF = 3)
![Import](captures/C2_import_100_films.png)

### Réplication (getendpoints)
![getendpoints](captures/C3_getendpoints.png)

### Niveaux de cohérence
![Consistency](captures/C4_consistency.png)

### Panne de cass3
![Panne](captures/C5_panne_cass3.png)

### Redémarrage de cass3
![Redémarrage](captures/C6_cass3_redemarre.png)
