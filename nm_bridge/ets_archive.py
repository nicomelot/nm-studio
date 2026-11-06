"""Read ETS project containers in memory; never extract or persist credentials.

ETS6 ZIP password derivation follows KNX project schema 21, ZipPassword.
"""
import base64
import hashlib
import io
import re
import zipfile
import zlib
from contextlib import contextmanager

MAX_PASSWORD_BYTES = 1024


def decode_upload(body, content_type, max_archive):
    """Versioned binary envelope: 4-byte password length, UTF-8 password, ZIP.

    Keep legacy octet-stream clients working without credentials in headers/URLs.
    """
    if content_type == "application/octet-stream":
        return body, ""
    if content_type != "application/vnd.nm.ets-upload" or len(body) < 4:
        raise ValueError("Formato richiesta ETS non valido")
    length = int.from_bytes(body[:4], "big")
    if length > MAX_PASSWORD_BYTES or len(body) < 4 + length:
        raise ValueError("Lunghezza password ETS non valida")
    try:
        password = body[4:4 + length].decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Codifica password ETS non valida") from None
    raw = body[4 + length:]
    if not 4 <= len(raw) <= max_archive:
        raise ValueError("Project file too large or empty")
    return raw, password


class ProjectArchive:
    def __init__(self, outer, overlays):
        self.outer = outer
        self.overlays = overlays

    def infolist(self):
        return self.outer.infolist() + [item[0] for item in self.overlays.values()]

    def namelist(self):
        return [info.filename for info in self.infolist()]

    def getinfo(self, name):
        if name in self.overlays:
            return self.overlays[name][0]
        return self.outer.getinfo(name)

    def read(self, member):
        name = member if isinstance(member, str) else member.filename
        if name in self.overlays:
            _, archive, original = self.overlays[name]
            return archive.read(original)
        return self.outer.read(member)


@contextmanager
def open_project(raw, password, max_members, max_xml, max_total):
    if not isinstance(password, str) or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password ETS troppo lunga o non valida")
    opened = []
    archive_errors = (zipfile.BadZipFile, zlib.error, EOFError, KeyError, NotImplementedError)
    try:
        outer = zipfile.ZipFile(io.BytesIO(raw))
        opened.append(outer)
        members = outer.infolist()
        if len(members) > max_members:
            raise ValueError("Too many archive entries")
        containers = [i for i in members if re.fullmatch(r"P-[0-9A-Fa-f]+\.zip", i.filename)]
        if len(containers) > 1:
            raise ValueError("Archivio con piu progetti: esporta un solo progetto ETS")
        overlays = {}
        for container in containers:
            if not password:
                raise ValueError("Progetto ETS protetto: inserisci la password del progetto e ripeti Analizza")
            if container.file_size > max_total:
                raise ValueError("Project exceeds XML safety limit")
            # Only the namespace is needed, not the potentially large master catalogue.
            with outer.open("knx_master.xml") as master:
                header = master.read(4096)
            schema = re.search(rb'https?://knx.org/xml/project/(\d+)', header)
            if not schema:
                raise ValueError("Versione del progetto ETS non riconosciuta")
            version = int(schema.group(1))
            if version >= 21:
                try:
                    import pyzipper
                except ImportError:
                    raise ValueError("Supporto cifratura ETS assente: aggiorna e ricostruisci NM Control") from None
                reader = pyzipper.AESZipFile
                archive_errors += (pyzipper.BadZipFile,)
                secret = base64.b64encode(hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-16-le"), b"21.project.ets.knx.org", 65536, 32))
            else:
                reader = zipfile.ZipFile
                secret = password.encode("utf-8")
            inner = reader(io.BytesIO(outer.read(container)))
            opened.append(inner)
            inner.setpassword(secret)
            if len(members) + len(inner.infolist()) > max_members:
                raise ValueError("Too many archive entries")
            total = 0
            for info in inner.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".xml"):
                    continue
                # ETS stores 0.xml and project.xml at the inner archive root.
                if "/" in info.filename or "\\" in info.filename:
                    raise ValueError("Percorso interno del progetto ETS non valido")
                if info.file_size > max_xml:
                    raise ValueError("Project XML too large")
                total += info.file_size
                if total > max_total:
                    raise ValueError("Project exceeds XML safety limit")
                virtual_name = container.filename[:-4] + "/" + info.filename
                if virtual_name in outer.namelist() or virtual_name in overlays:
                    raise ValueError("Elementi duplicati nel progetto ETS")
                virtual = zipfile.ZipInfo(virtual_name)
                virtual.file_size = info.file_size
                overlays[virtual_name] = (virtual, inner, info)
        yield ProjectArchive(outer, overlays)
    except RuntimeError:
        raise ValueError("Password ETS errata o mancante: riprova con la password del progetto") from None
    except archive_errors:
        raise ValueError("Archivio ETS danneggiato o formato non supportato: esporta nuovamente da ETS") from None
    finally:
        for archive in reversed(opened):
            archive.close()
