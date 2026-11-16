import hmac
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlsplit

import requests
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, desc
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import NullPool


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, instance_relative_config=True)
IS_PRODUCTION = (
    os.environ.get("RENDER", "").lower() == "true"
    or os.environ.get("FLASK_ENV", "").lower() == "production"
)
app.config.update(
    SECRET_KEY=(
        os.environ.get("FLASK_SECRET_KEY")
        or os.environ.get("SESSION_SECRET")
        or "local-development-secret-change-before-deploy"
    ),
    MAX_CONTENT_LENGTH=1_000_000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
)

if IS_PRODUCTION:
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_password or admin_password == "admin123":
        raise RuntimeError(
            "Set a private ADMIN_PASSWORD in Render before starting the production website."
        )
    if not os.environ.get("FLASK_SECRET_KEY"):
        raise RuntimeError("Set FLASK_SECRET_KEY in Render before starting the production website.")

os.makedirs(app.instance_path, exist_ok=True)

Base = declarative_base()


def build_database_url():
    configured_url = os.environ.get("DATABASE_URL")
    if configured_url:
        if configured_url.startswith("postgres://"):
            configured_url = configured_url.replace("postgres://", "postgresql://", 1)
        if configured_url.startswith("postgresql://"):
            # Key change: switch to psycopg (version 3) driver
            configured_url = configured_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        if "sslmode=" not in configured_url:
            separator = "&" if "?" in configured_url else "?"
            configured_url += f"{separator}sslmode=require"
        return configured_url
    

    database_path = os.environ.get(
        "DATABASE_PATH",
        os.path.join(app.instance_path, "standout.db"),
    )
    os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
    return f"sqlite:///{database_path}"


database_url = build_database_url()

engine_options = {
    "poolclass": NullPool,
}

if database_url.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(database_url, **engine_options)
DatabaseSession = sessionmaker(bind=engine, expire_on_commit=False)


class Conversation(Base):
    __tablename__ = "management_conversations"

    id = Column(Integer, primary_key=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(254), nullable=True)
    phone = Column(String(40), nullable=True)
    status = Column(String(16), nullable=False, default="open", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )

    @property
    def last_message(self):
        return self.messages[-1].body if self.messages else ""


class Message(Base):
    __tablename__ = "management_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("management_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender = Column(String(16), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_read_by_admin = Column(Boolean, nullable=False, default=False)
    conversation = relationship("Conversation", back_populates="messages")


class ContentPost(Base):
    __tablename__ = "content_posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    content_type = Column(String(32), nullable=False, default="article", index=True)
    summary = Column(String(400), nullable=False, default="")
    body = Column(Text, nullable=False)
    cover_image_url = Column(String(1000), nullable=True)
    status = Column(String(16), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True, index=True)


class PublicSubmission(Base):
    __tablename__ = "public_submissions"

    id = Column(Integer, primary_key=True)
    kind = Column(String(16), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(254), nullable=True)
    rating = Column(Integer, nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    post_id = Column(
        Integer,
        ForeignKey("content_posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


Base.metadata.create_all(engine)

CONTENT_TYPES = {
    "blog": "Blog post",
    "article": "Article",
    "news": "News",
    "project_update": "Project update",
    "other": "Other",
}


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def enforce_csrf():
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    expected = session.get("_csrf_token", "")
    supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        if request.is_json:
            return jsonify({"error": "Your session expired. Refresh the page and try again."}), 400
        abort(400, description="Your session expired. Refresh the page and try again.")
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def message_json(message):
    created = message.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": message.id,
        "sender": message.sender,
        "body": message.body,
        "created_at": created.isoformat(),
    }


def company_chat_fallback(text):
    """A company-specific response keeps the chat useful before a Cohere key is added."""
    question = text.lower()
    if any(word in question for word in ("where", "location", "address", "office", "visit")):
        return (
            "STANDOUT B&C is based at Park Plaza Building along Eastern Bypass in Utawala, Nairobi. "
            "Call 0731157929 if you would like to arrange a visit."
        )
    if any(word in question for word in (
        "service", "build", "renovat", "roof", "concrete", "kitchen", "bathroom",
        "commercial", "home", "extension", "framing", "interior", "fitout", "tiling",
        "paint", "gypsum", "cabinet", "door", "cladding", "subcontractor",
        "architectural", "structural", "mazeras", "plumbing", "electrical", "ruff", "tuff"
    )):
        return (
            "We offer a full range of construction and finishing services including: "
            "Interior design, Interior fit-out, General construction, Tiling works, Paint works, "
            "Gypsum work, Cabinet installation, Door installation, Timber cladding, Subcontracting, "
            "Architectural design, Structural design, Mazeras installation, Roofing, Plumbing, "
            "Electrical wiring, and Ruff n Tuff finishes. Tell me a little about your project, "
            "or use Chat with management for a direct reply."
        )
    if any(word in question for word in ("quote", "cost", "price", "estimate", "budget")):
        return (
            "Every project is different, so the team will need a little more detail before discussing "
            "scope and pricing. Send your project details through Chat with management or call "
            "0731157929."
        )
    if any(word in question for word in ("director", "engineer", "team", "who")):
        return (
            "The team includes Director CPM. Okolla Felix and Site Engineer B.Tech Frank Okotsi. "
            "STANDOUT B&C focuses on quality, integrity, safety, accountability and client needs."
        )
    if any(word in question for word in ("phone", "contact", "call", "whatsapp", "number")):
        return "You can reach STANDOUT B&C on 0731157929."
    if any(word in question for word in ("mission", "approach", "quality", "safety", "values")):
        return (
            "Our approach starts with understanding your goals, planning carefully, communicating "
            "openly and delivering with a focus on craftsmanship, safety and accountability."
        )
    return (
        "I can help with our services, Nairobi location, team and project process. For a detailed "
        "project discussion or a human reply, please message management or call 0731157929."
    )


def cohere_reply(message, history):
    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        return company_chat_fallback(message)

    company_context = (
        "You are the website assistant for STANDOUT B&C, a construction company in Nairobi, Kenya. "
        "Be warm, concise, professional, and clear. Answer only from the company facts below. "
        "Never invent pricing, project availability, guarantees, timelines, awards, portfolio items, "
        "or customer testimonials. For a quote, technical assessment, or project-specific commitment, "
        "ask the visitor to contact management at 0731157929 or use the management chat. "
        "Company facts: New home and custom home construction; commercial construction; renovations "
        "and remodels; additions and extensions; kitchen and bathroom remodeling; concrete and "
        "foundations; roofing; framing; project management; design-build services; light commercial "
        "and industrial work. Office: Park Plaza Building along Eastern Bypass, Utawala, Nairobi. "
        "Director: CPM. Okolla Felix. Site Engineer: B.Tech Frank Okotsi. Values: quality, integrity, "
        "safety, accountability, and client focus. The company plans and communicates clearly and "
        "works to keep projects on track and on budget."
    )
    messages = [{"role": "system", "content": company_context}]
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:1000]})
    messages.append({"role": "user", "content": message})

    try:
        response = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Client-Name": "standout-bc-website",
            },
            json={
                "model": os.environ.get("COHERE_MODEL", "command-a-03-2025"),
                "messages": messages,
                "stream": False,
                "max_tokens": 500,
                "temperature": 0.3,
            },
            timeout=35,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", [])
        reply = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if not reply:
            raise ValueError("Cohere returned an empty message.")
        return reply
    except requests.RequestException as error:
        app.logger.warning("Cohere request failed: %s", error.__class__.__name__)
        raise RuntimeError("The AI assistant is temporarily unavailable. Please message management.") from error
    except (KeyError, ValueError, TypeError) as error:
        app.logger.warning("Cohere response could not be read: %s", error.__class__.__name__)
        raise RuntimeError("The AI assistant could not prepare a response. Please message management.") from error


@app.get("/")
def home():
    with DatabaseSession() as db:
        recent_posts = (
            db.query(ContentPost)
            .filter_by(status="published")
            .order_by(desc(ContentPost.published_at), desc(ContentPost.id))
            .limit(3)
            .all()
        )
        recent_reviews = (
            db.query(PublicSubmission)
            .filter_by(kind="review", status="approved")
            .order_by(desc(PublicSubmission.created_at), desc(PublicSubmission.id))
            .limit(3)
            .all()
        )
        return render_template(
            "index.html",
            recent_posts=recent_posts,
            recent_reviews=recent_reviews,
        )


def make_slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:200].strip("-")


def save_public_submission(kind, post_id=None):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    body = request.form.get("body", "").strip()
    honeypot = request.form.get("website", "").strip()
    rating_value = request.form.get("rating", "").strip()

    if honeypot:
        return False
    if not name or len(name) > 100:
        flash("Please enter your name (up to 100 characters).", "error")
        return False
    if email and (len(email) > 254 or "@" not in email):
        flash("Please enter a valid email address or leave it blank.", "error")
        return False
    if not body or len(body) > 3000:
        flash("Please write a message of up to 3,000 characters.", "error")
        return False

    rating = None
    if kind == "review":
        try:
            rating = int(rating_value)
        except (TypeError, ValueError):
            rating = 0
        if rating < 1 or rating > 5:
            flash("Choose a rating from 1 to 5 stars.", "error")
            return False

    with DatabaseSession() as db:
        db.add(
            PublicSubmission(
                kind=kind,
                name=name,
                email=email or None,
                rating=rating,
                body=body,
                status="pending",
                post_id=post_id,
            )
        )
        db.commit()
    flash("Thank you. Your submission is waiting for management approval.", "success")
    return True


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/journal")
def journal():
    page = max(request.args.get("page", default=1, type=int), 1)
    per_page = 9
    with DatabaseSession() as db:
        query = db.query(ContentPost).filter_by(status="published")
        total = query.count()
        posts = (
            query.order_by(desc(ContentPost.published_at), desc(ContentPost.id))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
    return render_template(
        "journal.html",
        posts=posts,
        page=page,
        has_next=page * per_page < total,
        has_previous=page > 1,
    )


@app.route("/journal/<slug>", methods=["GET", "POST"])
def journal_post(slug):
    with DatabaseSession() as db:
        post = db.query(ContentPost).filter_by(slug=slug, status="published").first()
        if post is None:
            abort(404)
        if request.method == "POST":
            save_public_submission("comment", post_id=post.id)
            return redirect(url_for("journal_post", slug=post.slug) + "#comments")
        comments = (
            db.query(PublicSubmission)
            .filter_by(post_id=post.id, kind="comment", status="approved")
            .order_by(PublicSubmission.created_at.asc(), PublicSubmission.id.asc())
            .all()
        )
        return render_template("journal_post.html", post=post, comments=comments)


@app.route("/community", methods=["GET", "POST"])
def community():
    if request.method == "POST":
        kind = request.form.get("kind", "")
        if kind not in {"review", "comment"}:
            flash("Choose a review or comment before submitting.", "error")
        else:
            save_public_submission(kind)
        return redirect(url_for("community") + "#share")

    with DatabaseSession() as db:
        reviews = (
            db.query(PublicSubmission)
            .filter_by(kind="review", status="approved")
            .order_by(desc(PublicSubmission.created_at), desc(PublicSubmission.id))
            .all()
        )
        comments = (
            db.query(PublicSubmission)
            .filter_by(kind="comment", status="approved", post_id=None)
            .order_by(desc(PublicSubmission.created_at), desc(PublicSubmission.id))
            .limit(30)
            .all()
        )
    return render_template("community.html", reviews=reviews, comments=comments)


@app.post("/api/ai-chat")
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    history = data.get("history", [])
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please enter a message."}), 400
    if len(message) > 1500:
        return jsonify({"error": "Please keep your message under 1,500 characters."}), 400
    if not isinstance(history, list):
        history = []
    try:
        return jsonify({"reply": cohere_reply(message.strip(), history)})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503


@app.post("/api/management/conversations")
def start_management_conversation():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email", "")
    phone = data.get("phone", "")
    body = data.get("message")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return jsonify({"error": "Please enter your name."}), 400
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > 3000:
        return jsonify({"error": "Please enter a message under 3,000 characters."}), 400
    if not isinstance(email, str) or len(email) > 254 or not isinstance(phone, str) or len(phone) > 40:
        return jsonify({"error": "Please check your contact details."}), 400

    with DatabaseSession() as db:
        conversation = Conversation(
            token=secrets.token_urlsafe(32),
            name=name.strip(),
            email=email.strip() or None,
            phone=phone.strip() or None,
        )
        conversation.messages.append(
            Message(sender="visitor", body=body.strip(), is_read_by_admin=False)
        )
        db.add(conversation)
        db.commit()
        return jsonify(
            {
                "token": conversation.token,
                "messages": [message_json(conversation.messages[0])],
                "status": conversation.status,
            }
        ), 201


@app.get("/api/management/conversations/<token>")
def get_management_conversation(token):
    after = request.args.get("after", default=0, type=int)
    with DatabaseSession() as db:
        conversation = db.query(Conversation).filter_by(token=token).first()
        if conversation is None:
            return jsonify({"error": "This conversation could not be found."}), 404
        messages = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.id > max(after, 0),
            )
            .order_by(Message.id.asc())
            .all()
        )
        return jsonify(
            {
                "conversation_id": conversation.token,
                "messages": [message_json(message) for message in messages],
                "status": conversation.status,
            }
        )


@app.post("/api/management/conversations/<token>/messages")
def send_management_message(token):
    data = request.get_json(silent=True) or {}
    body = data.get("message")
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > 3000:
        return jsonify({"error": "Please enter a message under 3,000 characters."}), 400
    with DatabaseSession() as db:
        conversation = db.query(Conversation).filter_by(token=token).first()
        if conversation is None:
            return jsonify({"error": "This conversation could not be found."}), 404
        conversation.status = "open"
        conversation.updated_at = datetime.utcnow()
        message = Message(
            conversation=conversation,
            sender="visitor",
            body=body.strip(),
            is_read_by_admin=False,
        )
        db.add(message)
        db.commit()
        return jsonify({"message": message_json(message), "status": conversation.status}), 201


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_username = os.environ.get("ADMIN_USERNAME", "admin")
        expected_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        if hmac.compare_digest(username, expected_username) and hmac.compare_digest(
            password, expected_password
        ):
            session.clear()
            session["admin_authenticated"] = True
            session["admin_username"] = expected_username
            csrf_token()
            next_path = request.args.get("next", "")
            if next_path.startswith("/") and not next_path.startswith("//"):
                return redirect(next_path)
            return redirect(url_for("admin_dashboard"))
        flash("That username or password did not match.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["GET", "POST"])
@login_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@login_required
def admin_dashboard():
    with DatabaseSession() as db:
        conversations = (
            db.query(Conversation)
            .order_by(desc(Conversation.updated_at), desc(Conversation.id))
            .all()
        )
        return render_template(
            "admin_dashboard.html",
            conversations=conversations,
            selected_conversation=None,
            selected_messages=[],
        )


@app.get("/admin/conversations/<token>")
@login_required
def admin_conversation(token):
    with DatabaseSession() as db:
        conversations = (
            db.query(Conversation)
            .order_by(desc(Conversation.updated_at), desc(Conversation.id))
            .all()
        )
        selected = next((item for item in conversations if item.token == token), None)
        if selected is None:
            abort(404)
        selected.messages
        return render_template(
            "admin_dashboard.html",
            conversations=conversations,
            selected_conversation=selected,
            selected_messages=selected.messages,
        )


@app.post("/admin/conversations/<token>/reply")
@login_required
def admin_reply(token):
    body = request.form.get("message", "")
    if not body.strip() or len(body.strip()) > 3000:
        flash("Write a reply under 3,000 characters.", "error")
        return redirect(url_for("admin_conversation", token=token))
    with DatabaseSession() as db:
        conversation = db.query(Conversation).filter_by(token=token).first()
        if conversation is None:
            abort(404)
        conversation.updated_at = datetime.utcnow()
        db.add(
            Message(
                conversation=conversation,
                sender="admin",
                body=body.strip(),
                is_read_by_admin=True,
            )
        )
        db.commit()
    return redirect(url_for("admin_conversation", token=token))


@app.post("/admin/conversations/<token>/resolve")
@login_required
def resolve_conversation(token):
    with DatabaseSession() as db:
        conversation = db.query(Conversation).filter_by(token=token).first()
        if conversation is None:
            abort(404)
        conversation.status = "resolved"
        conversation.updated_at = datetime.utcnow()
        db.commit()
    return redirect(url_for("admin_conversation", token=token))


@app.post("/admin/conversations/<token>/reopen")
@login_required
def reopen_conversation(token):
    with DatabaseSession() as db:
        conversation = db.query(Conversation).filter_by(token=token).first()
        if conversation is None:
            abort(404)
        conversation.status = "open"
        conversation.updated_at = datetime.utcnow()
        db.commit()
    return redirect(url_for("admin_conversation", token=token))


@app.get("/admin/content")
@login_required
def admin_content():
    edit_id = request.args.get("edit", type=int)
    with DatabaseSession() as db:
        posts = (
            db.query(ContentPost)
            .order_by(desc(ContentPost.updated_at), desc(ContentPost.id))
            .all()
        )
        editing_post = db.query(ContentPost).filter_by(id=edit_id).first() if edit_id else None
        if edit_id and editing_post is None:
            abort(404)
        return render_template(
            "admin_content.html",
            posts=posts,
            editing_post=editing_post,
            content_types=CONTENT_TYPES,
        )


@app.post("/admin/content/save")
@login_required
def admin_content_save():
    post_id = request.form.get("post_id", type=int)
    title = request.form.get("title", "").strip()
    slug = make_slug(request.form.get("slug", "").strip() or title)
    content_type = request.form.get("content_type", "article")
    summary = request.form.get("summary", "").strip()
    body = request.form.get("body", "").strip()
    image_url = request.form.get("cover_image_url", "").strip()
    status = request.form.get("status", "draft")

    if not title or len(title) > 180 or not slug or len(slug) > 200:
        flash("Add a title and a URL-friendly slug.", "error")
        return redirect(url_for("admin_content", edit=post_id) if post_id else url_for("admin_content"))
    if content_type not in CONTENT_TYPES or status not in {"draft", "published"}:
        abort(400)
    if len(summary) > 400 or not body or len(body) > 30000:
        flash("Keep the summary under 400 characters and the article under 30,000 characters.", "error")
        return redirect(url_for("admin_content", edit=post_id) if post_id else url_for("admin_content"))
    if image_url:
        parsed_image_url = urlsplit(image_url)
        if parsed_image_url.scheme not in {"http", "https"} or not parsed_image_url.netloc:
            flash("Cover image must be a full http:// or https:// URL.", "error")
            return redirect(url_for("admin_content", edit=post_id) if post_id else url_for("admin_content"))

    with DatabaseSession() as db:
        post = db.query(ContentPost).filter_by(id=post_id).first() if post_id else ContentPost()
        if post_id and post is None:
            abort(404)
        duplicate = db.query(ContentPost).filter_by(slug=slug).first()
        if duplicate is not None and duplicate.id != post_id:
            flash("That URL slug is already in use. Choose another one.", "error")
            return redirect(url_for("admin_content", edit=post_id) if post_id else url_for("admin_content"))

        was_published = post.status == "published"
        post.title = title
        post.slug = slug
        post.content_type = content_type
        post.summary = summary
        post.body = body
        post.cover_image_url = image_url or None
        post.status = status
        post.updated_at = datetime.utcnow()
        if status == "published":
            if not was_published or post.published_at is None:
                post.published_at = datetime.utcnow()
        else:
            post.published_at = None
        db.add(post)
        db.commit()
    flash("Content saved.", "success")
    return redirect(url_for("admin_content", edit=post.id))


@app.post("/admin/content/<int:post_id>/delete")
@login_required
def admin_content_delete(post_id):
    with DatabaseSession() as db:
        post = db.query(ContentPost).filter_by(id=post_id).first()
        if post is None:
            abort(404)
        db.query(PublicSubmission).filter_by(post_id=post.id).update(
            {PublicSubmission.post_id: None},
            synchronize_session=False,
        )
        db.delete(post)
        db.commit()
    flash("Content deleted. Existing approved comments are kept in the community area.", "success")
    return redirect(url_for("admin_content"))


@app.get("/admin/submissions")
@login_required
def admin_submissions():
    status_filter = request.args.get("status", "pending")
    if status_filter not in {"pending", "approved", "all"}:
        status_filter = "pending"
    with DatabaseSession() as db:
        query = db.query(PublicSubmission)
        if status_filter != "all":
            query = query.filter_by(status=status_filter)
        submissions = query.order_by(
            desc(PublicSubmission.created_at),
            desc(PublicSubmission.id),
        ).all()
        pending_count = db.query(PublicSubmission).filter_by(status="pending").count()
        return render_template(
            "admin_submissions.html",
            submissions=submissions,
            status_filter=status_filter,
            pending_count=pending_count,
        )


@app.post("/admin/submissions/<int:submission_id>/approve")
@login_required
def admin_submission_approve(submission_id):
    with DatabaseSession() as db:
        submission = db.query(PublicSubmission).filter_by(id=submission_id).first()
        if submission is None:
            abort(404)
        submission.status = "approved"
        db.commit()
    flash("Submission approved and visible on the website.", "success")
    return redirect(url_for("admin_submissions"))


@app.post("/admin/submissions/<int:submission_id>/delete")
@login_required
def admin_submission_delete(submission_id):
    with DatabaseSession() as db:
        submission = db.query(PublicSubmission).filter_by(id=submission_id).first()
        if submission is None:
            abort(404)
        db.delete(submission)
        db.commit()
    flash("Submission deleted.", "success")
    return redirect(url_for("admin_submissions"))


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Please try again.")), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="The page you are looking for could not be found."), 404


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "The request is too large."}), 413


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "").lower() == "true",
    )
