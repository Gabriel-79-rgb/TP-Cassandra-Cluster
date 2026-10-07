import os
from dataclasses import dataclass, field
from typing import Optional

import requests
from cassandra.cluster import Cluster
from dotenv import load_dotenv


@dataclass
class Movie:
    """Modèle de données d'un film."""
    imdb_id: str
    title: str
    year: Optional[int]
    runtime: Optional[str]
    genres: list = field(default_factory=list)
    directors: list = field(default_factory=list)
    countries: list = field(default_factory=list)
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None

    @staticmethod
    def _split(value: Optional[str]) -> list:
        if not value or value == "N/A":
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    @staticmethod
    def _clean(value: Optional[str]) -> Optional[str]:
        return None if value in (None, "N/A", "") else value

    @classmethod
    def from_api(cls, d: dict) -> "Movie":
        year = cls._clean(d.get("Year"))
        rating = cls._clean(d.get("imdbRating"))
        votes = cls._clean(d.get("imdbVotes"))
        return cls(
            imdb_id=d["imdbID"],
            title=d.get("Title"),
            year=int(year) if year and year.isdigit() else None,
            runtime=cls._clean(d.get("Runtime")),
            genres=cls._split(d.get("Genre")),
            directors=cls._split(d.get("Director")),
            countries=list(dict.fromkeys(
                "United States" if c == "USA" else c
                for c in cls._split(d.get("Country"))
            )),
            imdb_rating=float(rating) if rating else None,
            imdb_votes=int(votes.replace(",", "")) if votes else None,
        )


class OmdbClient:
    """Interroge l'API OMDb (recherche puis détail)."""

    BASE_URL = "http://www.omdbapi.com/"

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, **params) -> dict:
        params["apikey"] = self.api_key
        r = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def search_ids(self, keyword: str, page: int = 1) -> list:
        data = self._get(s=keyword, type="movie", page=page)
        if data.get("Response") != "True":
            return []
        return [item["imdbID"] for item in data["Search"]]

    def get_movie(self, imdb_id: str) -> Optional[Movie]:
        data = self._get(i=imdb_id)
        if data.get("Response") != "True":
            return None
        return Movie.from_api(data)


class MovieRepository:
    """Accès Cassandra : écrit dans les 5 tables du keyspace movies."""

    def __init__(self, hosts=("127.0.0.1",), port=9042, keyspace="movies"):
        self.hosts = list(hosts)
        self.port = port
        self.keyspace = keyspace
        self.cluster = None
        self.session = None

    def connect(self) -> None:
        self.cluster = Cluster(self.hosts, port=self.port)
        self.session = self.cluster.connect(self.keyspace)
        s = self.session
        self.ins_movie = s.prepare(
            "INSERT INTO movies (imdb_id, title, year, runtime, genres, directors, "
            "countries, imdb_rating, imdb_votes) VALUES (?,?,?,?,?,?,?,?,?)")
        self.ins_director = s.prepare(
            "INSERT INTO movies_by_director (director, year, imdb_id, title, imdb_rating) "
            "VALUES (?,?,?,?,?)")
        self.ins_genre = s.prepare(
            "INSERT INTO movies_by_genre (genre, imdb_rating, imdb_id, title, year) "
            "VALUES (?,?,?,?,?)")
        self.ins_year = s.prepare(
            "INSERT INTO movies_by_year (year, imdb_rating, imdb_id, title) "
            "VALUES (?,?,?,?)")
        self.ins_genre_count = s.prepare(
            "INSERT INTO movies_by_genre_count (genre_count, imdb_id, title, genres) "
            "VALUES (?,?,?,?)")
        self.inc_country = s.prepare(
            "UPDATE movie_count_by_country SET nb_movies = nb_movies + 1 "
            "WHERE country = ?")

    def close(self) -> None:
        if self.cluster:
            self.cluster.shutdown()

    def reset_counters(self) -> None:
        """Les counters ne sont pas idempotents : on repart de zéro."""
        self.session.execute("TRUNCATE movie_count_by_country")

    def save(self, m: Movie) -> None:
        s = self.session
        s.execute(self.ins_movie, (
            m.imdb_id, m.title, m.year, m.runtime, m.genres, m.directors,
            m.countries, m.imdb_rating, m.imdb_votes))

        if m.year is not None:
            for d in m.directors:
                s.execute(self.ins_director,
                          (d, m.year, m.imdb_id, m.title, m.imdb_rating))
        if m.imdb_rating is not None:
            for g in m.genres:
                s.execute(self.ins_genre,
                          (g, m.imdb_rating, m.imdb_id, m.title, m.year))
        if m.year is not None and m.imdb_rating is not None:
            s.execute(self.ins_year, (m.year, m.imdb_rating, m.imdb_id, m.title))
        if m.genres:
            s.execute(self.ins_genre_count,
                      (len(m.genres), m.imdb_id, m.title, m.genres))
        for c in m.countries:
            s.execute(self.inc_country, (c,))

    def top_countries(self, n: int = 10) -> list:
        """REQ-04 : le tri se fait en Python."""
        rows = self.session.execute("SELECT country, nb_movies FROM movie_count_by_country")
        return sorted(rows, key=lambda r: r.nb_movies, reverse=True)[:n]

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class MovieImporter:
    """Orchestre : OMDb -> Python -> Cassandra."""

    def __init__(self, client: OmdbClient, repository: MovieRepository,
                 keywords: list, pages: int = 2):
        self.client = client
        self.repository = repository
        self.keywords = keywords
        self.pages = pages

    def collect_ids(self) -> list:
        ids = []
        for kw in self.keywords:
            for page in range(1, self.pages + 1):
                for imdb_id in self.client.search_ids(kw, page):
                    if imdb_id not in ids:
                        ids.append(imdb_id)
        return ids

    def run(self) -> None:
        print("Récupération des films OMDb...")
        ids = self.collect_ids()
        print(f"{len(ids)} films trouvés.")

        with self.repository as repo:
            repo.reset_counters()
            count = 0
            for imdb_id in ids:
                movie = self.client.get_movie(imdb_id)
                if movie is None:
                    continue
                repo.save(movie)
                count += 1
                print(f"Film importé : {movie.imdb_id} - {movie.title} ({movie.year})")

            print(f"Import terminé : {count} films.")
            print("\nTop des pays :")
            for row in repo.top_countries():
                print(f"  {row.country} : {row.nb_movies}")


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key:
        raise SystemExit("OMDB_API_KEY introuvable : vérifie ton fichier .env")

    importer = MovieImporter(
        client=OmdbClient(api_key),
        repository=MovieRepository(),
        keywords=["batman", "star", "love", "war", "night"],
        pages=2,
    )
    importer.run()
