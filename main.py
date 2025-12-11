from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# --- BASE DE DATOS ---
DATABASE_URL = "sqlite:///./latice_v3.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS (TABLAS) ---
class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    email = Column(String, unique=True, index=True) # <--- ¡NUEVO! Guardamos el correo
    facultad = Column(String)
    modo_faro = Column(Boolean, default=True)
    mision = Column(String)
    intereses_str = Column(String)

class MensajeDB(Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    de_usuario = Column(String)
    para_usuario = Column(String)
    texto = Column(String)

Base.metadata.create_all(bind=engine)

# --- APP ---
app = FastAPI(title="Latice API con Google Login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servimos el frontend en la ruta raíz


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- ESQUEMAS (Pydantic) ---
class UsuarioEntrada(BaseModel):
    nombre: str
    email: str  # <---  Recibimos el correo
    facultad: str
    modo_faro: bool
    mision: str
    intereses: List[str]

class MensajeEntrada(BaseModel):
    de_usuario: str
    para_usuario: str
    texto: str

# --- ENDPOINTS ---

# 1. NUEVO: Verificar si el usuario ya existe por su email
@app.get("/validar-google/{email}")
def validar_usuario_google(email: str, db: Session = Depends(get_db)):
    # Buscamos en la base de datos
    usuario = db.query(UsuarioDB).filter(UsuarioDB.email == email).first()
    
    if usuario:
        # Si existe, devolvemos sus datos clave
        return {"existe": True, "id": usuario.id, "nombre": usuario.nombre}
    else:
        # No existe
        return {"existe": False}

# 2. MODIFICADO: Registrar ahora guarda el email
@app.post("/registrar")
def registrar_usuario(usuario: UsuarioEntrada, db: Session = Depends(get_db)):
    # Convertimos lista de intereses a texto
    intereses_texto = ",".join([i.lower().strip() for i in usuario.intereses])
    
    # Creamos el usuario con email
    nuevo = UsuarioDB(
        nombre=usuario.nombre, 
        email=usuario.email, # <--- ¡AQUÍ SE GUARDA!
        facultad=usuario.facultad, 
        modo_faro=usuario.modo_faro, 
        mision=usuario.mision, 
        intereses_str=intereses_texto
    )
    
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"mensaje": "OK", "id": nuevo.id, "nombre": nuevo.nombre} # Ojo: cambié "id_asignado" por "id" para ser consistente

@app.get("/buscar-match/{usuario_id}")
def algoritmo_match(usuario_id: int, db: Session = Depends(get_db)):
    yo = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()
    if not yo: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    candidatos = db.query(UsuarioDB).filter(UsuarioDB.id != usuario_id, UsuarioDB.facultad == yo.facultad).all()
    resultados = []
    mis_intereses = set(yo.intereses_str.split(","))

    for persona in candidatos:
        sus_intereses = set(persona.intereses_str.split(","))
        comun = mis_intereses.intersection(sus_intereses)
        if len(comun) > 0:
            pct = (len(comun) / len(mis_intereses)) * 100
            resultados.append({"id": persona.id, "nombre": persona.nombre, "mision": persona.mision, "match_percent": round(pct, 1), "temas_comun": list(comun)})
    
    return {"usuario": yo.nombre, "top_matches": sorted(resultados, key=lambda x: x['match_percent'], reverse=True)}

# --- ENDPOINTS CHAT ---

@app.post("/enviar-mensaje")
def enviar(msg: MensajeEntrada, db: Session = Depends(get_db)):
    nuevo_msg = MensajeDB(de_usuario=msg.de_usuario, para_usuario=msg.para_usuario, texto=msg.texto)
    db.add(nuevo_msg); db.commit()
    return {"mensaje": "Enviado"}

@app.get("/leer-mensajes/{mi_nombre}/{contacto_nombre}")
def leer(mi_nombre: str, contacto_nombre: str, db: Session = Depends(get_db)):
    msgs = db.query(MensajeDB).filter(
        ((MensajeDB.de_usuario == mi_nombre) & (MensajeDB.para_usuario == contacto_nombre)) |
        ((MensajeDB.de_usuario == contacto_nombre) & (MensajeDB.para_usuario == mi_nombre))
    ).all()
    return msgs
app.mount("/", StaticFiles(directory=".", html=True), name="static")