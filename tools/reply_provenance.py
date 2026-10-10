"""Vinculación de texto GPT al destino y contexto de generación (PR #79).

No retiene textos, autores ni URLs: solo hashes. No prueba autenticidad frente
a procesos con permiso de escribir el registro. Legacy gpt_texts.json es
solo lectura y NUNCA autoriza respuestas.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
import time
from urllib.parse import urlsplit, parse_qs
from reply_state_lock import state_guard

VERSION = 1
TTL = 36 * 3600
KINDS = {"bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok"}
AT_URI = re.compile(r"at://did:(?:plc|web):[^/]+/app\.bsky\.feed\.post/[a-z0-9]+", re.I)


def norm_net(net):
    net = str(net or "").casefold().strip()
    return "reddit" if net == "reddit_micro" else net


def compact(s):
    return " ".join(s.split()) if isinstance(s, str) else ""


def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def path_for(path=None):
    if path:
        return os.fspath(path)
    if os.environ.get("RRSS_GPT_PROVENANCE_PATH"):
        return os.environ["RRSS_GPT_PROVENANCE_PATH"]
    old = os.environ.get("RRSS_GPT_TEXTS_PATH") or os.path.join(
        os.path.dirname(__file__), "..", "00_OPERATIVO", "_cola_respuestas", "gpt_texts.json")
    return os.path.join(os.path.dirname(os.path.abspath(old)), "gpt_provenance_v1.json")


def _domain(host, base):
    return host == base or host.endswith("." + base)


def canonical(net, obj):
    """Identidad de publicación; nunca ID ordinal de un escáner ni URL de perfil."""
    net = norm_net(net)
    if net not in KINDS or not isinstance(obj, dict):
        return ""
    native = obj.get("post_uri")
    if net == "bluesky" and isinstance(native, str) and AT_URI.fullmatch(native.strip()):
        return native.strip()
    if net == "mastodon":
        status = obj.get("status_id") or native
        if isinstance(status, (str, int)) and not isinstance(status, bool):
            s = str(status).strip()
            if (re.fullmatch(r"[A-Za-z0-9._-]{1,128}", s)
                    and not re.fullmatch(r"[GM]\d+-P\d+", s, flags=re.I)
                    and s not in (".", "..", "0")):
                return "mastodon:status:" + (str(int(s)) if s.isdecimal() else s)
    url = obj.get("permalink") or obj.get("url")
    if not isinstance(url, str):
        return ""
    try:
        u = urlsplit(url.strip())
        host, p = (u.hostname or "").lower().rstrip("."), u.path.rstrip("/")
        if (u.scheme != "https" or not p or not host or u.username or u.password
                or u.port or host in ("localhost", "127.0.0.1") or host.startswith("192.168.")):
            return ""
        query = ""
        if net == "bluesky":
            if host != "bsky.app" or not re.fullmatch(r"/profile/[^/]+/post/[^/]+", p):
                return ""
        elif net == "mastodon":
            if not re.search(r"/(?:@[^/]+/|statuses/)\d+$", p):
                return ""
        elif net == "x":
            if not (_domain(host, "x.com") or _domain(host, "twitter.com")) or not re.search(r"/status/\d+$", p):
                return ""
            host = "x.com"
        elif net == "threads":
            if not (_domain(host, "threads.net") or _domain(host, "threads.com")) or not re.search(r"/post/[^/]+$", p):
                return ""
            host = "threads.net"
        elif net == "facebook":
            if not (_domain(host, "facebook.com") or _domain(host, "fb.com")):
                return ""
            if p.endswith("/permalink.php"):
                ids = parse_qs(u.query).get("story_fbid", [])
                if len(ids) != 1 or not ids[0].isdigit():
                    return ""
                query = "?story_fbid=" + ids[0]
            elif not re.search(r"/(?:posts|permalink|videos)/[^/]+$", p):
                return ""
            host = "facebook.com"
        elif net == "pinterest":
            if not _domain(host, "pinterest.com") or not re.fullmatch(r"/pin/\d+", p):
                return ""
            host = "pinterest.com"
        elif net == "reddit":
            if not _domain(host, "reddit.com") or not re.search(r"/comments/[a-z0-9]+(?:/|$)", p, re.I):
                return ""
            ids = parse_qs(u.query).get("comment_id", [])
            if ids:
                if len(ids) != 1 or not re.fullmatch(r"(?:t1_)?[a-z0-9]+", ids[0], re.I):
                    return ""
                query = "?comment_id=" + ids[0].casefold()
            host = "reddit.com"
        elif net == "tiktok":
            if not _domain(host, "tiktok.com") or not re.search(r"/@[^/]+/video/\d+$", p):
                return ""
            host = "tiktok.com"
        return "https://" + host + p + query
    except (ValueError, TypeError, OverflowError):
        return ""


def source_hash(source):
    if not isinstance(source, dict) or not compact(source.get("text")):
        return ""
    fields = [compact(source.get("text")), compact(source.get("context")),
              compact(source.get("conversation_context")), bool(source.get("reply_to_us"))]
    return digest(json.dumps(fields, separators=(",", ":"), ensure_ascii=False))


def _identity(net, source, text):
    net, target = norm_net(net), canonical(net, source)
    ctx, phrase = source_hash(source), compact(text)
    if not target or not ctx or not phrase:
        return None
    ref_hash, text_hash = digest(target), digest(phrase)
    key = digest(json.dumps([VERSION, net, ref_hash, ctx, text_hash], separators=(",", ":")))
    return key, net, ref_hash, ctx, text_hash, digest(compact(source["text"]))


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("PROCEDENCIA_CORRUPTA")
    return data


def record(net, source, text, *, path=None, now=None, prompt_hash=None):
    identity = _identity(net, source, text)
    if not identity:
        return False
    key, name, ref_hash, ctx, text_hash, source_text_hash = identity
    if prompt_hash is not None and not re.fullmatch(r"[a-f0-9]{64}", prompt_hash):
        return False
    path, when = path_for(path), time.time() if now is None else float(now)
    try:
        # Mismo guard de la cola (#105); no bloquear durante la consulta GPT.
        with state_guard(path, timeout=3):
            data = {k: v for k, v in _load(path).items()
                    if isinstance(v, dict) and v.get("version") == VERSION
                    and isinstance(v.get("expires"), (int, float)) and v["expires"] > when}
            existing = data.get(key)
            # Mismo texto+post+contexto bajo OTRO prompt no debe poder
            # reetiquetar una generación anterior como si usase el prompt nuevo.
            # Sin identificador por invocación, el caso ambiguo falla cerrado.
            if existing and existing.get("prompt_hash") != (prompt_hash or ""):
                return False
            data[key] = {"version": VERSION, "network": name, "target_hash": ref_hash,
                         "context_hash": ctx, "text_hash": text_hash,
                         "source_text_hash": source_text_hash,
                         "prompt_hash": prompt_hash or "", "prompt_version": VERSION,
                         "expires": when + TTL, "state": "issued"}
            directory = os.path.dirname(os.path.abspath(path))
            os.makedirs(directory, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".proof-", suffix=".tmp", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp, path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return True
    except (OSError, ValueError, TimeoutError):
        return False


def verify(action, net, *, path=None, now=None):
    if not isinstance(action, dict):
        return False
    name, ref, proof = norm_net(net), canonical(net, action), action.get("gpt_proof")
    if name not in KINDS or not ref or not isinstance(proof, str) or len(proof) != 64:
        return False
    try:
        entry = _load(path_for(path)).get(proof)
        t = time.time() if now is None else float(now)
        if (not isinstance(entry, dict) or entry.get("version") != VERSION
                or entry.get("network") != name or entry.get("state") != "issued"
                or not isinstance(entry.get("expires"), (int, float))
                or not (entry["expires"]-TTL-300 <= t < entry["expires"])):
            return False
        if (entry.get("target_hash") != digest(ref)
                or entry.get("text_hash") != digest(compact(action.get("text")))
                or entry.get("context_hash") != action.get("gpt_context_hash")
                or entry.get("prompt_hash") != action.get("gpt_prompt_hash")):
            return False
        if "post_text" in action and entry.get("source_text_hash") != digest(compact(action["post_text"])):
            return False
        expected = digest(json.dumps([VERSION, name, entry["target_hash"],
                                      entry["context_hash"], entry["text_hash"]], separators=(",", ":")))
        return expected == proof
    except (OSError, ValueError, TypeError, KeyError):
        return False


def attach(action, source, net, *, path=None, now=None):
    """Prueba sobre acción final; origen cambiado, caducado o inexistente => None."""
    if not isinstance(action, dict) or not isinstance(source, dict):
        return None
    parts = _identity(net, source, action.get("text"))
    if not parts or canonical(net, action) != canonical(net, source):
        return None
    try:
        issued = _load(path_for(path)).get(parts[0])
        if not isinstance(issued, dict):
            return None
        result = dict(action, gpt_proof=parts[0], gpt_context_hash=parts[3],
                      gpt_prompt_hash=issued.get("prompt_hash"), post_text=source["text"])
        return result if verify(result, net, path=path, now=now) else None
    except (OSError, ValueError, TypeError):
        return None

PROOF_FIELDS = ("gpt_proof", "gpt_context_hash", "gpt_prompt_hash", "post_text")


def carry_decision_proof(action, decision, network, scanned_text=None, *, source_limit=600):
    """Conserva una prueba solo si el post reconstruido y el texto leído coinciden.

    Una decisión antigua sin prueba se deja al guard final (se abstendrá).
    Una prueba parcial/falsa se descarta sin detener las demás acciones.
    """
    if not isinstance(action, dict) or not isinstance(decision, dict):
        return None
    if not any(field in decision for field in PROOF_FIELDS[:3]):
        return action
    if not all(isinstance(decision.get(field), str) for field in PROOF_FIELDS):
        return None
    if scanned_text is not None:
        read = compact(scanned_text)[:source_limit]
        if read != compact(decision["post_text"]):
            return None
    candidate = dict(action)
    candidate.update({field: decision[field] for field in PROOF_FIELDS})
    return candidate if verify(candidate, network) else None
