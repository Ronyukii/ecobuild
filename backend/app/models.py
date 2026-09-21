from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey
from .database import Base

class CPU(Base):
    __tablename__ = "cpu"
    cpu_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    socket = Column(String(20), nullable=False)
    tdp_watts = Column(Integer, nullable=False)
    base_score = Column(Integer, nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class Motherboard(Base):
    __tablename__ = "motherboard"
    mobo_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    socket = Column(String(20), nullable=False)
    form_factor = Column(String(20), nullable=False)
    ram_type = Column(String(10), nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class GPU(Base):
    __tablename__ = "gpu"
    gpu_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    pcie_slot = Column(String(20), nullable=False)
    tdp_watts = Column(Integer, nullable=False)
    base_score = Column(Integer, nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class Cooler(Base):
    __tablename__ = "cooler"
    cooler_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    socket_list = Column(String, nullable=False)
    max_tdp = Column(Integer, nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class Case(Base):
    __tablename__ = "case"
    case_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    form_factor = Column(String(20), nullable=False)
    airflow_coef = Column(Numeric(3, 2), nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class RAM(Base):
    __tablename__ = "ram"
    ram_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    ram_type = Column(String(10), nullable=False)
    capacity_gb = Column(Integer, nullable=False)
    speed_mhz = Column(Integer, nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class Storage(Base):
    __tablename__ = "storage"
    storage_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    capacity_gb = Column(Integer, nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class PSU(Base):
    __tablename__ = "psu"
    psu_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    wattage = Column(Integer, nullable=False)
    efficiency = Column(String(20), nullable=False)
    price = Column(Numeric(7, 2), nullable=False)

class ScrapedPrice(Base):
    __tablename__ = "scraped_price"
    price_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_key = Column(String(50), nullable=False)
    platform = Column(String(20), nullable=False)
    price_rm = Column(Numeric(7, 2), nullable=False)
    shipping_rm = Column(Numeric(5, 2), nullable=False)
    is_available = Column(Boolean, default=True)
    sample_count = Column(Integer, default=1)