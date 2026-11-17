import os
from pathlib import Path
from decimal import Decimal
import urllib.error
import streamlit as st
from dotenv import load_dotenv
from client import complete

load_dotenv(Path(__file__).with_name(".env"))
st.set_page_config(page_title="OCI · LiteLLM demó", page_icon="☁️")
st.title("OCI · LiteLLM demó")
st.caption("Streamlit → LiteLLM → OCI Generative AI / Cohere Command A")
base_url = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
api_key = os.getenv("LITELLM_API_KEY", "")
model = os.getenv("LITELLM_MODEL", "oci-cohere")
if not api_key or "REPLACE" in api_key:
    st.error("Állítsd be a LiteLLM virtuális kulcsát az app/.env fájlban.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.costs = []

with st.sidebar:
    st.subheader("Beállítások")
    system = st.text_area("Rendszerutasítás", "Segítőkész asszisztens vagy. Válaszolj magyarul.")
    max_tokens = st.slider("Maximum válasz-token", 100, 4000, 1000, 100)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    total = sum((c for c in st.session_state.costs if c is not None), Decimal(0))
    st.metric("Munkamenet ismert LLM-költsége", f"${total:.8f}")
    if any(c is None for c in st.session_state.costs):
        st.warning("Az összeg részleges: van költségadat nélküli kérés.")
    st.caption("A LiteLLM által visszaadott USD-becslés. A VM-ek és a hálózat díját nem tartalmazza. A tartós kimutatás a LiteLLM adatbázisában van.")
    if st.button("Új beszélgetés"):
        st.session_state.messages = []
        st.session_state.costs = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("accounting"):
            st.caption(message["accounting"])

if prompt := st.chat_input("Írj egy kérdést vagy promptot…", max_chars=50000):
    user_message = {"role": "user", "content": prompt}
    with st.chat_message("user"):
        st.markdown(prompt)
    # Only commit this turn after success; API receives no UI accounting metadata.
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    try:
        with st.chat_message("assistant"), st.spinner("Válasz az OCI modelljétől…"):
            result = complete(base_url, api_key, model,
                              [{"role": "system", "content": system}, *history, user_message],
                              max_tokens=max_tokens, temperature=temperature)
            cost_text = f"${result.cost_usd:.8f}" if result.cost_usd is not None else "nem érkezett költségadat"
            accounting = f"Input: {result.prompt_tokens} token · Output: {result.completion_tokens} token · LiteLLM: {cost_text} · Azonosító: {result.request_id}"
            st.markdown(result.text)
            st.caption(accounting)
            if result.cost_usd is None:
                st.warning("Hiányzik az x-litellm-response-cost fejléc; ellenőrizd a proxy árbeállítását és a Spend Logs nézetet.")
        st.session_state.messages.extend([user_message, {"role": "assistant", "content": result.text, "accounting": accounting}])
        st.session_state.costs.append(result.cost_usd)
        st.rerun()
    except urllib.error.HTTPError as exc:
        status = exc.code
        hints = {401: "Hibás vagy lejárt LiteLLM kulcs.", 402: "Elfogyott a virtuális kulcs költségkerete.",
                 403: "Ellenőrizd a kulcs modelljogosultságát és az OCI IAM szabályokat.",
                 429: "Elérted a sebesség- vagy kvótakorlátot. Próbáld később."}
        st.error(f"HTTP {status}: {hints.get(status, 'A proxy vagy az OCI hibát jelzett; nézd meg a proxy naplóját.')} A kérés nem indul újra automatikusan.")
    except (urllib.error.URLError, TimeoutError, OSError):
        st.error("Kapcsolati hiba vagy időtúllépés. Ellenőrizd a proxy címét, a security listet és a VM-eket. Időtúllépésnél az OCI már feldolgozhatta a kérést; az app nem próbálja újra automatikusan.")
    except (ValueError, KeyError, IndexError, TypeError):
        st.error("A proxy válasza nem a várt chat/completions formátumú. Ellenőrizd a proxy naplóját.")
