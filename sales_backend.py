"""Corporate sales persistence: local JSON or server-only Supabase RPC."""
from __future__ import annotations
import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import streamlit as st
import sales_store


def settings():
    try:
        config = dict(st.secrets.get("sales_storage", {}))
    except FileNotFoundError:
        config = {}
    mode = config.get("backend", "local")
    if mode not in ("local", "supabase"):
        raise ValueError("Unknown sales storage backend.")
    if config.get("require_supabase") and mode != "supabase":
        raise ValueError("This deployment must store records in Supabase. Configure sales_storage in Streamlit Secrets.")
    if mode == "supabase":
        url = config.get("url", "").rstrip("/")
        key = config.get("secret_key", "")
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url) or not key.startswith("sb_secret_"):
            raise ValueError("Configure the Supabase project URL and server secret key in Streamlit Secrets.")
        config["url"] = url
    config["backend"] = mode
    return config


def storage_label():
    return "Supabase" if settings().get("backend") == "supabase" else "this computer"


def call(config, function, payload):
    """POST a server-only RPC; map failures to user-facing errors."""
    request = Request(config["url"] + "/rest/v1/rpc/" + function,
        data=json.dumps(payload).encode(), method="POST",
        headers={"apikey": config["secret_key"], "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 409:
            raise ValueError("Records changed in another session. Reload before saving.") from None
        raise OSError("Supabase rejected the request. Ask the administrator to check the connection and database setup.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise OSError("Supabase could not confirm the request. Reload saved records before retrying; a save may have completed.") from None


def rpc(config, function, payload):
    result = call(config, function, payload)
    if not isinstance(result, dict) or result.get("schema_version") != 1 or not all(k in result for k in ("revision", "companies", "orders", "targets", "history")):
        raise ValueError("Supabase returned an unexpected record format. Saving has been stopped.")
    return result


def read_store(path):
    config = settings()
    if config.get("backend") != "supabase":
        return sales_store.read_store(path)
    return rpc(config, "marathon_sales_read", {})


def save_store(path, data, expected_revision, action):
    config = settings()
    if config.get("backend") != "supabase":
        return sales_store.save_store(path, data, expected_revision, action)
    for order in data["orders"]:
        sales_store.validate_order(order)
    return rpc(config, "marathon_sales_save", {"p_data": data,
        "p_expected_revision": expected_revision, "p_action": action})
