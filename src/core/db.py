from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class PokemonSpecies(Base):
    __tablename__ = 'species'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True, nullable=False) # e.g. "bulbasaur"
    name = Column(String, nullable=False) # Display name
    
    # Base Stats
    base_hp = Column(Integer, nullable=False)
    base_attack = Column(Integer, nullable=False)
    base_defense = Column(Integer, nullable=False)
    base_sp_attack = Column(Integer, nullable=False)
    base_sp_defense = Column(Integer, nullable=False)
    base_speed = Column(Integer, nullable=False)
    
    # Types
    type1_id = Column(Integer, nullable=False)
    type2_id = Column(Integer, nullable=True) # Null if mono-type
    
    # Abilities (Gen 3 has up to 2)
    ability1_id = Column(Integer, nullable=False)
    ability2_id = Column(Integer, nullable=True)
    
    # Metadata
    catch_rate = Column(Integer)
    exp_yield = Column(Integer)
    gender_ratio = Column(Integer) # -1, 0, 127, 254, 255 etc.
    
class Move(Base):
    __tablename__ = 'moves'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    
    type_id = Column(Integer, nullable=False)
    power = Column(Integer, nullable=False)
    pp = Column(Integer, nullable=False)
    accuracy = Column(Integer, nullable=False)
    priority = Column(Integer, default=0)
    target_id = Column(Integer, nullable=False)
    effect_id = Column(Integer, nullable=False)
    effect_accuracy = Column(Integer)
    
    # Categorization
    split = Column(Integer) # 0=Physical, 1=Special, 2=Status (In Gen 3 this is Type-dependent, but good to store)
    
class Ability(Base):
    __tablename__ = 'abilities'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    
class Type(Base):
    __tablename__ = 'types'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    damage_class = Column(Integer) # 0=Physical, 1=Special (Gen 3 rules)

class Item(Base):
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)

# Database Setup
engine = create_engine('sqlite:///data/battle_factory.db')

def init_db():
    Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
