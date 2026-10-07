import os

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from dotenv import load_dotenv

from getapi import OmdbClient


class ClusterMovieRepository:
    """Écrit dans movies_cluster.movies (cluster 3 nœuds, RF=3)."""

    INSERT_CQL = (
        "INSERT INTO movies (imdb_id, title, year, runtime, genres, directors, "
        "countries, imdb_rating, imdb_votes) VALUES (?,?,?,?,?,?,?,?,?)"
    )

    def __init__(self, hosts=("127.0.0.1",), port=9042,
                 keyspace="movies_cluster"):
        self.hosts = list(hosts)
        self.port = port
        self.keyspace = keyspace

    def __enter__(self):
        self.cluster = Cluster(self.hosts, port=self.port)
        self.session = self.cluster.connect(self.keyspace)
        self.session.default_consistency_level = ConsistencyLevel.QUORUM
        self._insert = self.session.prepare(self.INSERT_CQL)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cluster.shutdown()

    def save(self, m) -> None:
        self.session.execute(self._insert, (
            m.imdb_id, m.title, m.year, m.runtime, m.genres, m.directors,
            m.countries, m.imdb_rating, m.imdb_votes))


class ClusterImporter:
    def __init__(self, client, repository, keywords, pages=2):
        self.client = client
        self.repository = repository
        self.keywords = keywords
        self.pages = pages

    def collect_ids(self):
        ids = []
        for kw in self.keywords:
            for page in range(1, self.pages + 1):
                for imdb_id in self.client.search_ids(kw, page):
                    if imdb_id not in ids:
                        ids.append(imdb_id)
        return ids

    def run(self):
        print("Récupération des films OMDb...")
        ids = self.collect_ids()
        print(f"{len(ids)} films trouvés.")
        with self.repository as repo:
            for imdb_id in ids:
                movie = self.client.get_movie(imdb_id)
                if movie is None:
                    continue
                repo.save(movie)
                print(f"Film importé : {movie.imdb_id} - {movie.title}")
        print("Import terminé.")


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key:
        raise SystemExit("OMDB_API_KEY introuvable : vérifie ton fichier .env")
    ClusterImporter(
        client=OmdbClient(api_key),
        repository=ClusterMovieRepository(),
        keywords=["batman", "star", "love", "war", "night"],
    ).run()
