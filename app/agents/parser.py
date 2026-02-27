import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from app.schemas import (
    ScreenplayDocument,
    ScreenplayElement,
    ScreenplayMetadata,
    ElementType,
)

load_dotenv()
client = OpenAI()


def parse_fountain(raw_text: str, title: str = "Untitled") -> ScreenplayDocument:
    """
    Recebe o texto bruto de um arquivo .fountain e retorna
    um ScreenplayDocument com todos os elementos identificados e sinalizados.
    """

    system_prompt = """You are a screenplay parser specialized in the Fountain format.
Your job is to analyze a Fountain screenplay and return a structured JSON.

Fountain format rules:
- SCENE HEADINGS start with INT., EXT., INT./EXT., I/E or EST.
- CHARACTER names are in ALL CAPS, alone on a line, before dialogue
- PARENTHETICALS are in (parentheses) between character and dialogue
- DIALOGUE follows a character name
- TRANSITIONS are in ALL CAPS ending with TO: or are FADE OUT. / FADE IN.
- NOTES are wrapped in [[ ]]
- PAGE BREAKS are === alone on a line
- Everything else is ACTION

Return ONLY a valid JSON array of elements, no explanation, no markdown, no code blocks.

Each element must have:
- "id": sequential string like "el_001", "el_002"
- "type": one of: scene_heading, action, character, parenthetical, dialogue, transition, note, page_break
- "original": the exact text of the element
- "translate": true or false

Translation rules:
- scene_heading: true
- character: false
- transition: false
- note: false
- page_break: false
- action: true
- parenthetical: true
- dialogue: true"""

    user_prompt = f"""Parse this Fountain screenplay into structured JSON elements:

{raw_text}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    raw_json = response.choices[0].message.content.strip()
    raw_json = re.sub(r"```json|```", "", raw_json).strip()

    elements_data = json.loads(raw_json)

    elements = []
    for el in elements_data:
        elements.append(
            ScreenplayElement(
                id=el["id"],
                type=ElementType(el["type"]),
                original=el["original"],
                translated=None,
                translate=el["translate"],
            )
        )

    return ScreenplayDocument(
        metadata=ScreenplayMetadata(
            title=title,
            source_language="en",
            target_language="pt-BR",
            original_format="fountain",
        ),
        elements=elements,
    )