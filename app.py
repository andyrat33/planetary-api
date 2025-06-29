import subprocess
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float
import os
from flask_marshmallow import Marshmallow
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from flask_mail import Mail, Message


DOES_NOT_EXIST = "That planet does not exist"

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir, "planets.db"
)
app.config["JWT_SECRET_KEY"] = "super-secret"  # change this IRL
app.config["MAIL_SERVER"] = "smtp.mailtrap.io"
app.config["MAIL_USERNAME"] = os.environ["MAIL_USERNAME"]
app.config["MAIL_PASSWORD"] = os.environ["MAIL_PASSWORD"]
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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


@app.cli.command("db_seed")
def db_seed():
    mercury = Planet(
        planet_name="Mercury",
        planet_type="Class D",
        home_star="Sol",
        mass=2.258e23,
        radius=1516,
        distance=35.98e6,
    )

    vulcan = Planet(
        planet_name="Vulcan",
        planet_type="Class M",
        home_star="Sol",
        mass=2.258e23,
        radius=1516,
        distance=35.98e6,
    )

    ferenginar = Planet(
        planet_name="Ferenginar",
        planet_type="Class M",
        home_star="Plub",
        mass=6.258e23,
        radius=3516,
        distance=367.98e6,
    )

    venus = Planet(
        planet_name="Venus",
        planet_type="Class K",
        home_star="Sol",
        mass=4.86457e24,
        radius=3760,
        distance=67.24e6,
    )

    earth = Planet(
        planet_name="Earth",
        planet_type="Class M",
        home_star="Sol",
        mass=5.97269e24,
        radius=3959,
        distance=92.96e6,
    )
    romulus = Planet(
        planet_name="Romulus",
        planet_type="Class M",
        home_star="Romulus Star",
        mass=5.9772e24,
        radius=3339569,
        distance=92.96e6,
    )
    klingon = Planet(
        planet_name="Klingon",
        planet_type="Class M",
        home_star="Klingon Star",
        mass=5.962e24,
        radius=433959,
        distance=995.96e6,
    )
    db.session.add(mercury)
    db.session.add(vulcan)
    db.session.add(venus)
    db.session.add(earth)
    db.session.add(ferenginar)
    db.session.add(romulus)
    db.session.add(klingon)

    test_user = User(
        first_name="William",
        last_name="Herschel",
        email="test@test.com",
        password="P@ssw0rd",
    )

    test_user2 = User(
        first_name="Brian",
        last_name="Herschel",
        email="test2@test.com",
        password="password123",
    )

    db.session.add(test_user)
    db.session.add(test_user2)
    db.session.commit()
    print("Database seeded!")


# @app.route("/")
# def hello_world():
#     return "Planetary-API!"


@app.route("/", methods=["GET"])
def serve_frontend():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Planetary API</title>
    </head>
    <body>
        <h2>Login</h2>
        <input type="text" id="email" placeholder="Email">
        <input type="password" id="password" placeholder="Password">
        <button onclick="login()">Login</button>
        <h2>Get Planet</h2>
        <input type="text" id="planet_name" placeholder="Planet Name">
        <button onclick="getPlanet()">Fetch Planet</button>

        <h2>Add Planet</h2>
        <input type="text" id="new_planet_name" placeholder="Planet Name">
        <input type="text" id="new_planet_type" placeholder="Planet Type">
        <input type="text" id="new_home_star" placeholder="Home Star">
        <input type="number" id="new_mass" placeholder="Mass">
        <input type="number" id="new_radius" placeholder="Radius">
        <input type="number" id="new_distance" placeholder="Distance">
        <button onclick="addPlanet()">Add Planet</button>

        <h2>Delete Planet</h2>
        <input type="number" id="delete_planet_id" placeholder="Planet ID">
        <button onclick="deletePlanet()">Delete Planet</button>

        <pre id="output"></pre>
        <script>
            let token = "";
            function login() {
                const email = document.getElementById("email").value;
                const password = document.getElementById("password").value;
                fetch("/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ "email": email,
                        "password": password })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.access_token) {
                        token = data.access_token;
                        alert("Login successful");
                    } else {
                        alert("Invalid credentials");
                    }
                });
            }
            function getPlanet() {
                const planet_name = document.getElementById("planet_name")
                .value;
                fetch(`/get_planet/${planet_name}`, {
                    headers: { "Authorization": `Bearer ${token}` }
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById("output").textContent =
                    JSON.stringify(data, null, 2);
                });
            }

            function addPlanet() {
                const body = {
                    planet_name: document.getElementById("new_planet_name").value,
                    planet_type: document.getElementById("new_planet_type").value,
                    home_star: document.getElementById("new_home_star").value,
                    mass: document.getElementById("new_mass").value,
                    radius: document.getElementById("new_radius").value,
                    distance: document.getElementById("new_distance").value,
                };
                fetch("/add_planet", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify(body)
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById("output").textContent =
                    JSON.stringify(data, null, 2);
                });
            }

            function deletePlanet() {
                const planet_id = document.getElementById("delete_planet_id").value;
                fetch(`/remove_planet/${planet_id}`, {
                    method: "DELETE",
                    headers: { "Authorization": `Bearer ${token}` }
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById("output").textContent =
                    JSON.stringify(data, null, 2);
                });
            }
        </script>
    </body>
    </html>
    """


@app.route("/get_planet/<string:planet_name>", methods=["GET"])
@jwt_required
def get_planet(planet_name: str):
    """Get planet details by name"""
    if not planet_name:
        return jsonify(message="Missing planet name"), 400

    planet = Planet.query.filter_by(planet_name=planet_name).first()
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
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)


class Planet(db.Model):
    __tablename__ = "planets"
    planet_id = Column(Integer, primary_key=True)
    planet_name = Column(String)
    planet_type = Column(String)
    home_star = Column(String)
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


if __name__ == "__main__":
    app.run()
