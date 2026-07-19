import os
from flask import Flask
from config import Config
from app.extensions import db

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(config_class)

    db.init_app(app)

    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.inventory import inventory_bp
    from app.routes.purchase import purchase_bp
    from app.routes.chat import chat_bp
    from app.routes.upload import upload_bp
    from app.routes.suppliers import suppliers_bp
    from app.routes.insights import insights_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(purchase_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(insights_bp)

    # Initialize the RAG knowledge base (ChromaDB) once at startup
    with app.app_context():
        from app.rag.retriever import init_knowledge_base
        init_knowledge_base(app.config["CHROMA_DB_PATH"])

    return app
