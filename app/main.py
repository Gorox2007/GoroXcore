from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = auth.decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


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


@app.post("/token", response_model=schemas.Token, include_in_schema=False)
def login_with_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 Password Grant for Swagger "Authorize" button.

    Uses username as email; returns same JWT as /login.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth.create_access_token({"sub": user.email})
    return schemas.Token(access_token=token)


@app.get("/users", response_model=list[schemas.UserOut])
def list_users(
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.User).all()


@app.patch("/users/me", response_model=schemas.UserOut)
def update_me(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.first_name is not None:
        current_user.first_name = payload.first_name
    if payload.last_name is not None:
        current_user.last_name = payload.last_name
    if payload.password is not None:
        current_user.hashed_password = auth.get_password_hash(payload.password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
