USE movies_cluster;

CONSISTENCY ONE;
SELECT imdb_id, title, year FROM movies LIMIT 1;

CONSISTENCY QUORUM;
SELECT imdb_id, title, year FROM movies LIMIT 1;

CONSISTENCY ALL;
SELECT imdb_id, title, year FROM movies LIMIT 1;
