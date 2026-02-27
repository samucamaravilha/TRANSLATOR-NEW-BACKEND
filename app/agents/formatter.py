import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from app.schemas import ScreenplayDocument, ElementType


def format_fountain(document: ScreenplayDocument) -> str:
    """
    Reconstrói o arquivo .fountain a partir do ScreenplayDocument traduzido.
    """

    lines = []

    for el in document.elements:
        text = el.translated if el.translated is not None else el.original

        if el.type == ElementType.SCENE_HEADING:
            lines.append(f"\n{text}\n")

        elif el.type == ElementType.ACTION:
            lines.append(f"\n{text}\n")

        elif el.type == ElementType.CHARACTER:
            lines.append(f"\n{text}")

        elif el.type == ElementType.PARENTHETICAL:
            lines.append(f"{text}")

        elif el.type == ElementType.DIALOGUE:
            lines.append(f"{text}\n")

        elif el.type == ElementType.TRANSITION:
            lines.append(f"\n{text}\n")

        elif el.type == ElementType.NOTE:
            lines.append(f"\n[[{text}]]\n")

        elif el.type == ElementType.PAGE_BREAK:
            lines.append("\n===\n")

    return "\n".join(lines)


def format_pdf(fountain_text: str, title: str = "Untitled") -> bytes:
    """
    Gera um PDF a partir do texto .fountain.
    Aplica formatação visual padrão de roteiro: Courier 12pt, margens corretas.
    """

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Margens padrão de roteiro
    left_margin = 1.5 * inch
    right_margin = width - 1.0 * inch
    top_margin = height - 1.0 * inch
    bottom_margin = 1.0 * inch
    usable_width = right_margin - left_margin

    c.setFont("Courier", 12)
    line_height = 14
    y = top_margin

    def new_page():
        nonlocal y
        c.showPage()
        c.setFont("Courier", 12)
        y = top_margin

    def write_line(text, x=None):
        nonlocal y
        if y < bottom_margin:
            new_page()
        c.drawString(x or left_margin, y, text)
        y -= line_height

    # Título centralizado no topo
    c.setFont("Courier-Bold", 14)
    c.drawCentredString(width / 2, y, title.upper())
    y -= line_height * 2
    c.setFont("Courier", 12)

    for line in fountain_text.split("\n"):
        stripped = line.strip()

        if not stripped:
            y -= line_height / 2
            continue

        # Scene heading
        if re.match(r"^(INT\.|EXT\.|INT\./EXT\.)", stripped):
            y -= line_height / 2
            write_line(stripped.upper())
            y -= line_height / 2

        # Nome do personagem — caixa alta, indentado ao centro
        elif re.match(r"^[A-Z][A-Z\s]+$", stripped) and len(stripped) < 40:
            write_line(stripped, x=3.5 * inch)

        # Parenthetical
        elif stripped.startswith("(") and stripped.endswith(")"):
            write_line(stripped, x=3.0 * inch)

        # Transição
        elif re.match(r".+TO:$|^FADE (IN|OUT)\.$", stripped):
            text_width = c.stringWidth(stripped, "Courier", 12)
            write_line(stripped, x=right_margin - text_width)

        # Page break
        elif stripped == "===":
            y -= line_height

        # Action ou Dialogue — quebra de linha automática
        else:
            words = stripped.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                if c.stringWidth(test_line, "Courier", 12) <= usable_width:
                    current_line = test_line
                else:
                    write_line(current_line)
                    current_line = word
            if current_line:
                write_line(current_line)

    c.save()
    buffer.seek(0)
    return buffer.read()