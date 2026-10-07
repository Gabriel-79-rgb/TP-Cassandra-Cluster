USE movies_cluster;

CONSISTENCY ALL;
SELECT imdb_id, title, year FROM movies LIMIT 1;

CONSISTENCY QUORUM;
INSERT INTO movies (imdb_id, title, year, runtime, genres, directors, countries, imdb_rating, imdb_votes)
VALUES ('tt9999999', 'Film Test Panne', 2026, '90 min', ['Drama'], ['Jean Test'], ['France'], 7.0, 100);

SELECT imdb_id, title FROM movies WHERE imdb_id = 'tt9999999';
