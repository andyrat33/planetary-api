import subprocess
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float
import os
from flask_marshmallow import Marshmallow
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from flask_mail import Mail, Message
import logging
import json
import requests
import httpx
from urllib.parse import urlparse


DOES_NOT_EXIST = "That planet does not exist"

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://{}:{}@{}/{}".format(
    os.environ["DB_USER"],
    os.environ["DB_PASSWORD"],
    os.environ["DB_HOST"],
    os.environ["DB_NAME"],
)
app.config["JWT_SECRET_KEY"] = "super-secret"  # change this IRL
app.config["MAIL_SERVER"] = "smtp.mailtrap.io"
app.config["MAIL_USERNAME"] = os.environ["MAIL_USERNAME"]
app.config["MAIL_PASSWORD"] = os.environ["MAIL_PASSWORD"]
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.logger.setLevel(logging.INFO)
# TDDO: store secrets in Amazon Secrets Manager or similar service

db = SQLAlchemy(app)
ma = Marshmallow(app)
jwt = JWTManager(app)
mail = Mail(app)


@app.cli.command("db_create")
def db_create():
    db.create_all()
    print("Database created!")


@app.cli.command("db_drop")
def db_drop():
    db.drop_all()
    print("Database dropped!")

    # python
    @app.cli.command("db_seed")
    def db_seed():
        try:
            # Load planets
            with open("star_trek_planets.json", "r") as f:
                planets_data = json.load(f)
            for planet_data in planets_data:
                new_planet = Planet(
                    planet_name=planet_data["planet_name"],
                    planet_type=planet_data["planet_type"],
                    home_star=planet_data["home_star"],
                    mass=planet_data["mass"],
                    radius=planet_data["radius"],
                    distance=planet_data["distance"],
                )
                db.session.add(new_planet)

            # Load users
            with open("users.json", "r") as f:
                users_data = json.load(f)
            for user_data in users_data:
                new_user = User(
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    email=user_data["email"],
                    password=user_data["password"],
                )
                db.session.add(new_user)

            db.session.commit()
            print("Database seeded!")

        except FileNotFoundError as e:
            print(f"Error: {e}")
        except json.JSONDecodeError as e:
            print(f"Error: Failed to decode JSON. {e}")
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")


# Done: Add a parameterized get request to allow SQLMAP to be used to demonstrate SQLi.
# This is for educational purposes only, do not use in production.
# Example: /get_planet_sqlmap?planet_name=Earth' OR '1'='1--
@app.route("/get_planet_sqlmap", methods=["GET"])
def get_planet_sqlmap():
    planet_name = request.args.get("planet_name", "")
    if not planet_name:
        return jsonify(message="Missing planet name"), 400

    with db.engine.connect() as con:
        planet = con.execute(
            "SELECT * from planets WHERE planet_name='{planet_name}'".format(
                planet_name=planet_name
            )
        ).first()
        app.logger.info(f"Planet: {planet}")
    if planet:
        result = planet_schema.dump(planet)
        return jsonify(result.data), 200
    else:
        return jsonify(message=DOES_NOT_EXIST), 404


@app.route("/", methods=["GET"])
def serve_frontend():
    return render_template("index.html")


@app.route("/random_planet", methods=["GET"])
def random_planet():
    # return a random planet_name
    import random

    result = random.choice(Planet.query.all()).planet_name
    return jsonify(planet_name=result), 200


@app.route("/get_planet/<string:planet_name>", methods=["GET"])
@jwt_required
def get_planet(planet_name: str):
    """Get planet details by name"""
    if not planet_name:
        return jsonify(message="Missing planet name"), 400

    # planet = Planet.query.filter_by(planet_name=planet_name).first()
    with db.engine.connect() as con:
        planet = con.execute(
            "SELECT * from planets WHERE planet_name='{planet_name}'".format(
                planet_name=planet_name
            )
        ).first()
        app.logger.info(f"Planet: {planet}")
    if planet:
        result = planet_schema.dump(planet)
        return jsonify(result.data), 200
    else:
        return jsonify(message=DOES_NOT_EXIST), 404


@app.route("/planetary")
def planetary():
    return "Planetary-API!"


@app.route("/not_found")
def not_found():
    return jsonify(message="That resource was not found"), 404


@app.route("/planets", methods=["GET"])
def planets():
    planets_list = Planet.query.all()
    result = planets_schema.dump(planets_list)
    return jsonify(result.data), 200


@app.route("/register", methods=["POST"])
def register():
    email = request.form["email"]
    test = User.query.filter_by(email=email).first()
    if test:
        return jsonify(message="That email already exists."), 409
    else:
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        password = request.form["password"]
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )
        db.session.add(user)
        db.session.commit()
        return jsonify(message="User created successfully."), 201


# @app.route("/login", methods=["POST"])
# def login():
#     """SQLAlchemy safe login"""
#     if request.is_json:
#         email = request.json["email"]
#         password = request.json["password"]
#     else:
#         email = request.form["email"]
#         password = request.form["password"]
#
#     test = User.query.filter_by(email=email, password=password).first()
#     if test:
#         access_token = create_access_token(identity=email)
#         app.logger.info("%s logged in successfully", email)
#         return jsonify(message="Login succeeded!", access_token=access_token)
#     else:
#         app.logger.info("%s failed to log in", email)
#         return jsonify(message="Bad email or password"), 401


@app.route("/login", methods=["POST"])
def login():
    """insecure login. SQLi"""
    if request.is_json:
        email = request.json["email"]
        password = request.json["password"]
        print(f"email: {email}, password: {password}")
    else:
        email = request.form["email"]
        password = request.form["password"]
    with db.engine.connect() as con:
        test = con.execute(
            "SELECT * from users WHERE email='{id}' "
            "AND password='{passw}'".format(id=email, passw=password)
        ).first()
    app.logger.info(
        "SELECT * from users WHERE "
        "email='{id}' AND password length='{passw}'".format(
            id=email, passw=len(password)
        )
    )
    if test:
        access_token = create_access_token(identity=email)
        app.logger.info("%s logged in successfully", email)
        return jsonify(message="Login succeeded!", access_token=access_token)
    else:
        app.logger.info("%s failed to log in", email)
        return jsonify(message="Bad email or password"), 401


@app.route("/retrieve_password/<string:email>", methods=["GET"])
def retrieve_password(email: str):
    user = User.query.filter_by(email=email).first()
    if user:
        msg = Message(
            "your planetary API password is " + user.password,
            sender="admin@planetary-api.com",
            recipients=[email],
        )
        mail.send(msg)
        return jsonify(message="Password sent to " + email)
    else:
        return jsonify(message="That email doesn't exist"), 401


@app.route("/planet_details/<int:planet_id>", methods=["GET"])
def planet_details(planet_id: int):
    planet = Planet.query.filter_by(planet_id=planet_id).first()
    if planet:
        result = planet_schema.dump(planet)
        return jsonify(result.data)
    else:
        return jsonify(message=DOES_NOT_EXIST), 404


@app.route("/add_planet", methods=["POST"])
@jwt_required
def add_planet():
    if request.is_json:
        request_command = request.json
    else:
        request_command = request.form
    try:
        planet_name = request_command["planet_name"]
        planet_type = request_command["planet_type"]
        home_star = request_command["home_star"]
        mass = float(request_command["mass"])
        radius = float(request_command["radius"])
        distance = float(request_command["distance"])
    except Exception as e:
        return jsonify(message="Missing Parameter", errno=str(e)), 400

    if not planet_name:
        return jsonify(message="missing planet name"), 400

    test = Planet.query.filter_by(planet_name=planet_name).first()
    if test:
        return jsonify(message="There is already a planet by that name"), 409
    else:
        new_planet = Planet(
            planet_name=planet_name,
            planet_type=planet_type,
            home_star=home_star,
            mass=mass,
            radius=radius,
            distance=distance,
        )

        db.session.add(new_planet)
        db.session.commit()
        return (
            jsonify(message="You added a planet", id=new_planet.planet_id),
            201,
        )


@app.route("/update_planet", methods=["PUT"])
@jwt_required
def update_planet():
    if request.is_json:
        request_command = request.json
    else:
        request_command = request.form

    try:
        planet_id = request_command["planet_id"]
        planet_name = request_command["planet_name"]
        planet_type = request_command["planet_type"]
        home_star = request_command["home_star"]
        mass = float(request_command["mass"])
        radius = float(request_command["radius"])
        distance = float(request_command["distance"])
    except Exception as e:
        return jsonify(message="Missing Parameter", errno=str(e)), 400

    planet = Planet.query.filter_by(planet_id=planet_id).first()
    if planet:
        planet.planet_name = planet_name
        planet.planet_type = planet_type
        planet.home_star = home_star
        planet.mass = mass
        planet.radius = radius
        planet.distance = distance
        db.session.commit()
        return jsonify(message="You updated a planet"), 202
    else:
        return jsonify(message=DOES_NOT_EXIST), 404


@app.route("/remove_planet/<int:planet_id>", methods=["DELETE"])
@jwt_required
def remove_planet(planet_id: int):
    planet = Planet.query.filter_by(planet_id=planet_id).first()
    if planet:
        db.session.delete(planet)
        db.session.commit()
        return jsonify(message="You deleted a planet"), 202
    else:
        return jsonify(message=DOES_NOT_EXIST), 404


# @app.route("/dbsize/<string:dbfile>", methods=["GET"])
# def dbsize(dbfile: str):
#     """Secure version no command injection"""
#     try:
#         result = subprocess.check_output(["du", dbfile], shell=False)
#     except subprocess.CalledProcessError:
#         result = {"message": "Error"}
#         return jsonify(result), 400
#     return result, 200


@app.route("/dbsize/<string:dbfile>", methods=["GET"])
def dbsize(dbfile: str):
    """insecure command injection and XSS"""
    try:
        result = subprocess.check_output("du " + dbfile, shell=True)
    except subprocess.CalledProcessError:
        result = {"message": "Error"}
        return jsonify(result), 400
    return result, 200


# database models
class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    email = Column(String(120), unique=True)
    password = Column(String(120))


class Planet(db.Model):
    __tablename__ = "planets"
    planet_id = Column(Integer, primary_key=True)
    planet_name = Column(String(60))
    planet_type = Column(String(60))
    home_star = Column(String(60))
    mass = Column(Float)
    radius = Column(Float)
    distance = Column(Float)


class UserSchema(ma.Schema):
    class Meta:
        fields = ("id", "first_name", "last_name", "email", "password")


class PlanetSchema(ma.Schema):
    class Meta:
        fields = (
            "planet_id",
            "planet_name",
            "planet_type",
            "home_star",
            "mass",
            "radius",
            "distance",
        )


user_schema = UserSchema()
users_schema = UserSchema(many=True)

planet_schema = PlanetSchema()
planets_schema = PlanetSchema(many=True)


@app.route("/fetch")
def fetch():
    # ❌ Vulnerable: Directly using user input in a server-side request
    target_url = request.args.get("url")
    if not target_url:
        return "Missing 'url' parameter", 400

    try:
        # This can be exploited to access internal services
        resp = requests.get(target_url)
        return resp.text
    except requests.RequestException as e:
        return f"Error fetching URL: {e}", 500


@app.route("/fetch/safe")
def fetch_safe():
    # ✅ Safe: Validate user input before using it in a server-side request
    # uses httpx with URL validation
    target_url = request.args.get("url")
    if not target_url:
        return "Missing 'url' parameter", 400
    try:
        parsed_url = urlparse(target_url)
        if parsed_url.scheme not in ("http", "https"):
            return "Invalid URL scheme", 400
        if parsed_url.hostname in ("localhost", "example.com") and parsed_url.port in (
            80,
            443,
        ):
            return "Access to this host is not allowed", 403
        resp = httpx.get(target_url)
        return resp.text
    except httpx.RequestError as e:
        return f"Error fetching URL: {e}", 500


if __name__ == "__main__":
    app.run()
