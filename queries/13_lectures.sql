USE movies_cluster;

CONSISTENCY ONE;
SELECT imdb_id, title, year FROM movies WHERE imdb_id = 'tt0372784';

CONSISTENCY QUORUM;
SELECT imdb_id, title, year FROM movies WHERE imdb_id = 'tt0372784';

CONSISTENCY ALL;
SELECT imdb_id, title, year FROM movies WHERE imdb_id = 'tt0372784';

