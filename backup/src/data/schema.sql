CREATE TABLE IF NOT EXISTS species (
    id INTEGER PRIMARY KEY,
    identifier TEXT NOT NULL,
    name TEXT NOT NULL,
    type1 TEXT NOT NULL,
    type2 TEXT NOT NULL,
    base_hp INTEGER NOT NULL,
    base_atk INTEGER NOT NULL,
    base_def INTEGER NOT NULL,
    base_sp_atk INTEGER NOT NULL,
    base_sp_def INTEGER NOT NULL,
    base_speed INTEGER NOT NULL,
    ability1 TEXT,
    ability2 TEXT,
    UNIQUE(identifier)
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY,
    identifier TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    power INTEGER NOT NULL,
    accuracy INTEGER NOT NULL,
    pp INTEGER NOT NULL,
    effect TEXT NOT NULL,
    UNIQUE(identifier)
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    identifier TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE(identifier)
);

CREATE TABLE IF NOT EXISTS battle_frontier_mons (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL,
    move1_id INTEGER NOT NULL,
    move2_id INTEGER NOT NULL,
    move3_id INTEGER NOT NULL,
    move4_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    nature TEXT NOT NULL,
    ev_spread INTEGER NOT NULL,
    FOREIGN KEY(species_id) REFERENCES species(id),
    FOREIGN KEY(move1_id) REFERENCES moves(id),
    FOREIGN KEY(move2_id) REFERENCES moves(id),
    FOREIGN KEY(move3_id) REFERENCES moves(id),
    FOREIGN KEY(move4_id) REFERENCES moves(id),
    FOREIGN KEY(item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS type_efficacy (
    attacker_type TEXT NOT NULL,
    defender_type TEXT NOT NULL,
    damage_factor REAL NOT NULL,
    PRIMARY KEY (attacker_type, defender_type)
);
