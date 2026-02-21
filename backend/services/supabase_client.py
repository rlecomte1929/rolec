import os
from supabase import create_client, Client


def get_supabase_client(user_jwt: str) -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required")

    client = create_client(supabase_url, supabase_key)
    try:
        client.postgrest.auth(user_jwt)
    except Exception:
        try:
            client.postgrest.session.headers.update(
                {"Authorization": f"Bearer {user_jwt}"}
            )
        except Exception:
            pass
    return client
