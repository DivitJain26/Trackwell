"""Blueprint registration."""


def register_blueprints(app):
    from app.routes import (admin, alerts, auth, dashboard, imports, interventions, main, model,
                            portal, predictions, students)

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(students.bp)
    app.register_blueprint(imports.bp)
    app.register_blueprint(predictions.bp)
    app.register_blueprint(alerts.bp)
    app.register_blueprint(interventions.bp)
    app.register_blueprint(model.bp)
    app.register_blueprint(portal.bp)
