import requests
from uuid import uuid4
import pronotepy
from urllib.parse import urlparse, urlunparse

from .pronotepy_monlycee import ile_de_france
from pronotepy.ent import ent_auvergnerhonealpe
from ..geocoding.geocoder import get_timezone_from_state
from ..verify_manual_link import clean_url
import logging

logger = logging.getLogger(__name__)


def _normalize_login_link(link: str) -> str | None:
    """Normalize provided link to a single pronote/eleve.html path."""
    cleaned = clean_url(link)
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/")

    if path.endswith("/eleve"):
        path = path.rsplit("/", 1)[0]

    segments = [seg for seg in path.split("/") if seg]
    if not segments or segments[-1].lower() != "pronote":
        path = "/pronote"
    else:
        path = "/" + "/".join(segments)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        f"{path}/eleve.html",
        "",
        "",
        ""
    ))

def check_if_ent(link: str) -> bool:
    """
    Check if the provided link is an ENT link.
    """
    response = requests.get(link, allow_redirects=False, timeout=15)

    if response.status_code == 302:
        return True
    elif response.status_code == 200:
        return False
    else:
        return None

def get_student_data(client: pronotepy.Client, ent_used: bool, qr_code_login: bool, uuid: str, region: str):
    student_fullname = client.info.name
    student_class = client.info.class_name
    login_page_link = client.pronote_url

    user_username = client.username
    user_password = client.password

    try:
        timezone = get_timezone_from_state(region)
    except Exception as e:
        logger.error(f"An error occurred while trying to get the timezone from state: '{e}' -> (Timezone set to default)")
        timezone = "Europe/Paris"

    if student_fullname:
        words = student_fullname.strip().split()
        for word in words:
            if not word.isupper() and word != "-":
                student_firstname = word
                break
            else:
                student_firstname = "None"

    return {
        "student_fullname": student_fullname,
        "student_firstname": student_firstname,
        "student_class": student_class,
        "login_page_link": login_page_link,
        "student_username": user_username,
        "student_password": user_password,
        "ent_used": ent_used,
        "qr_code_login": qr_code_login,
        "uuid": uuid,
        "timezone": timezone
    }


def global_pronote_login(link: str, username: str, password: str, qr_code_login: bool, qrcode_data: dict, pin: int, region: str):

    normalized_link = _normalize_login_link(link)
    if not normalized_link:
        return {"error": "Invalid login page link"}, 400

    if isinstance(password, (bytes, bytearray)):
        password = password.decode("utf-8", errors="strict")

    is_ent_login = check_if_ent(normalized_link)

    qr_code_login = bool(qr_code_login)

    if qr_code_login and pin and qrcode_data:
        uuid = uuid4()
        client = pronotepy.Client.qrcode_login(qrcode_data, pin, str(uuid))

        if client.logged_in:
            return get_student_data(client, ent_used=False, qr_code_login=True, uuid=str(uuid), region=region)
        else:
            return {"error": "QR code login failed"}, 400

    elif is_ent_login:
        logger.debug("Attempting ENT login")

        if is_ent_login is None:
            return {"error": "Invalid login page link"}, 400

        if region is None or region == "":
            return {"error": "Region is required for ENT login"}, 400

        if region == "Île-de-France" or region == "https://psn.monlycee.net":
            logger.debug("Using Île-de-France ENT settings")
            client = pronotepy.Client(normalized_link, username=username, password
