"""
MiroFish Backend - Flask application factory
"""

import os
import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libraries such as transformers)
# Set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask application factory function"""
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../frontend/dist')
    )
    has_frontend_dist = os.path.isdir(frontend_dist)

    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Set JSON encoding: ensure Chinese displays directly (not \uXXXX format)
    # Flask >= 2.3 uses app.json.ensure_ascii, older versions use JSON_AS_ASCII configuration
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Set logging
    logger = setup_logger('mirofish')
    
    # Only print startup info in reloader child process (avoid printing twice in debug mode)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend starting...")
        logger.info("=" * 50)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register simulation process cleanup function (ensure all simulation processes terminate when server shuts down)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registered simulation process cleanup function")
    
    # Request logging middleware
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, models_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(models_bp, url_prefix='/api/models')
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Serve the built SPA and support deep-link refreshes."""
        if not has_frontend_dist:
            return {
                'status': 'frontend_not_built',
                'message': 'Frontend dist not found. Run `npm run build` in frontend/ or use the Vite dev server.'
            }, 503

        candidate = os.path.join(frontend_dist, path)
        if path and os.path.isfile(candidate):
            return send_from_directory(frontend_dist, path)

        return send_from_directory(frontend_dist, 'index.html')
    
    if should_log_startup:
        logger.info("MiroFish Backend startup complete")
    
    return app
