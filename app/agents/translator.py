import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from app.schemas import ScreenplayDocument

load_dotenv()
client = OpenAI()

CHUNK_SIZE = 30


def translate_screenplay(document: ScreenplayDocument) -> ScreenplayDocument:
    """
    Recebe um ScreenplayDocument parseado e traduz todos os elementos
    com translate=True do inglês para o português brasileiro.
    Processa em chunks com janela de contexto local para suportar roteiros longos
    sem estourar o limite de tokens por minuto.
    """

    elements_to_translate = [el for el in document.elements if el.translate]

    if not elements_to_translate:
        return document

    # Divide os elementos em chunks
    chunks = [
        elements_to_translate[i: i + CHUNK_SIZE]
        for i in range(0, len(elements_to_translate), CHUNK_SIZE)
    ]

    translation_map = {}

    for index, chunk in enumerate(chunks):
        print(f"Traduzindo chunk {index + 1}/{len(chunks)}...")

        # Janela de contexto: 20 elementos antes e depois do chunk atual
        chunk_start_index = document.elements.index(chunk[0])
        chunk_end_index = document.elements.index(chunk[-1])

        context_start = max(0, chunk_start_index - 20)
        context_end = min(len(document.elements), chunk_end_index + 20)
        context_window = document.elements[context_start:context_end]

        context_block = "\n".join(
            [f"[{el.id}] ({el.type.value}): {el.original}" for el in context_window]
        )

        translation_block = json.dumps(
            [
                {"id": el.id, "type": el.type.value, "original": el.original}
                for el in chunk
            ],
            ensure_ascii=False,
            indent=2,
        )

        system_prompt = """You are a professional screenplay translator specializing in English to Brazilian Portuguese.

Your job is to translate screenplay elements naturally and contextually, preserving:
- Each character's unique voice, tone, and speech patterns
- Dramatic intent and emotional subtext
- Colloquialisms and idiomatic expressions adapted to Brazilian Portuguese
- The rhythm of dialogue as it would be spoken

Rules:
- Do NOT translate character names
- In scene headings, ALWAYS keep INT., EXT., INT./EXT. as is — only translate the location and time of day (e.g. "INT. POLICE STATION - NIGHT" becomes "INT. DELEGACIA - NOITE")
- Adapt expressions naturally — do not translate literally
- Maintain the register of each character (formal/informal/regional)
- Return ONLY a valid JSON array, no explanation, no markdown, no code blocks

Each item in the array must have:
- "id": same id as the original
- "translated": the Brazilian Portuguese translation"""

        user_prompt = f"""Here is the surrounding context for reference:

{context_block}

---

This is chunk {index + 1} of {len(chunks)}. Translate ONLY these elements to Brazilian Portuguese:

{translation_block}"""

        response = client.chat.completions.create(
            model="gpt-5.2-chat-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        raw_json = response.choices[0].message.content.strip()
        raw_json = re.sub(r"```json|```", "", raw_json).strip()

        translations = json.loads(raw_json)
        for item in translations:
            translation_map[item["id"]] = item["translated"]

    # Preenche os campos translated no documento
    for el in document.elements:
        if el.translate and el.id in translation_map:
            el.translated = translation_map[el.id]
        elif not el.translate:
            el.translated = el.original

    return document