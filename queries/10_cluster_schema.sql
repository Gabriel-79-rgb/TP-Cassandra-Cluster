CREATE KEYSPACE IF NOT EXISTS movies_cluster
WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};

USE movies_cluster;

CREATE TABLE IF NOT EXISTS movies (
    imdb_id text PRIMARY KEY,
    title text,
    year int,
    runtime text,
    genres list<text>,
    directors list<text>,
    countries list<text>,
    imdb_rating double,
    imdb_votes int
);
