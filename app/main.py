from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .database import Base, SessionLocal, engine

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="User Auth Service",
    description="Simple registration and login service with JWT tokens",
    version="1.0.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to Swagger UI to avoid 404."""
    return RedirectResponse(url="/docs")


@app.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = auth.get_password_hash(payload.password)
    user = models.User(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        hashed_password=hashed_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token({"sub": user.email})
    return schemas.Token(access_token=token)


@app.post("/login", response_model=schemas.Token)
def login_user(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth.create_access_token({"sub": user.email})
    return schemas.Token(access_token=token)
