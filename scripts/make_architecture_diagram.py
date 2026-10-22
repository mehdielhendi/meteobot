"""Generate METEOBOT architecture diagram (Figure 3.1) as PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path("docs")
OUT = OUT_DIR / "figure_3_1_architecture_meteobot.png"
OUT_PROJECT = Path("docs/figure_3_1_architecture_meteobot.png")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_box(draw, xy, fill, outline, width=2, radius=14):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, box, lines, fonts, fill):
    x0, y0, x1, y1 = box
    total_h = 0
    sizes = []
    for line, fnt in zip(lines, fonts):
        bbox = draw.textbbox((0, 0), line, font=fnt)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        sizes.append((w, h))
        total_h += h + 4
    total_h -= 4
    y = y0 + (y1 - y0 - total_h) // 2
    for (line, fnt), (w, h) in zip(zip(lines, fonts), sizes):
        x = x0 + (x1 - x0 - w) // 2
        draw.text((x, y), line, font=fnt, fill=fill)
        y += h + 4


def arrow(draw, start, end, fill):
    draw.line([start, end], fill=fill, width=4)
    x0, y0 = start
    x1, y1 = end
    if abs(x1 - x0) >= abs(y1 - y0):
        # horizontal
        direction = 1 if x1 > x0 else -1
        tip = (x1, y1)
        draw.polygon(
            [
                tip,
                (x1 - 14 * direction, y1 - 8),
                (x1 - 14 * direction, y1 + 8),
            ],
            fill=fill,
        )
    else:
        direction = 1 if y1 > y0 else -1
        tip = (x1, y1)
        draw.polygon(
            [
                tip,
                (x1 - 8, y1 - 14 * direction),
                (x1 + 8, y1 - 14 * direction),
            ],
            fill=fill,
        )


def main() -> None:
    W, H = 1600, 980
    img = Image.new("RGB", (W, H), "#0b1522")
    draw = ImageDraw.Draw(img)

    # subtle grid
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill="#122033", width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill="#122033", width=1)

    title_f = font(36, bold=True)
    sub_f = font(20)
    box_title = font(22, bold=True)
    box_body = font(17)
    small = font(15)
    tiny = font(14)

    title = "Figure 3.1 — Architecture globale de METEOBOT"
    subtitle = "Données DRMNO (PDF / JSON)  →  Backend FastAPI  →  Interface conversationnelle"
    tw = draw.textbbox((0, 0), title, font=title_f)[2]
    draw.text(((W - tw) // 2, 28), title, font=title_f, fill="#e8eef5")
    sw = draw.textbbox((0, 0), subtitle, font=sub_f)[2]
    draw.text(((W - sw) // 2, 78), subtitle, font=sub_f, fill="#8aa0b5")

    # Layer labels
    layers = [
        (60, "1. Couche données", "#3d9ecb"),
        (560, "2. Couche traitement (FastAPI)", "#7ec8e6"),
        (1060, "3. Couche présentation", "#9aebc4"),
    ]
    for x, label, color in layers:
        draw.text((x, 130), label, font=box_title, fill=color)

    # --- Data layer boxes ---
    data_boxes = [
        (60, 180, 300, 290, "Bulletins PDF", ["OBSMET horaire / quotidien", "SPECIAL 72h (villes)", "BMSGeneral (vigilance)"]),
        (60, 320, 300, 420, "Ingestion", ["scripts/ingest_*.py", "PDF → JSON structuré"]),
        (60, 450, 300, 580, "Stores locaux", ["hourly.json / daily.json", "special_forecasts.json", "bms_alerts.json"]),
    ]
    for box in data_boxes:
        x0, y0, x1, y1, head, lines = box
        rounded_box(draw, (x0, y0, x1, y1), "#142536", "#3d9ecb", 2)
        draw.text((x0 + 16, y0 + 14), head, font=box_title, fill="#7ec8e6")
        y = y0 + 52
        for line in lines:
            draw.text((x0 + 16, y), "• " + line, font=box_body, fill="#c9d7e6")
            y += 28

    # arrows data internal
    arrow(draw, (180, 290), (180, 318), "#5a7f9a")
    arrow(draw, (180, 420), (180, 448), "#5a7f9a")

    # --- Processing layer ---
    api_box = (420, 220, 900, 560)
    rounded_box(draw, api_box, "#132437", "#7ec8e6", 3)
    draw.text((440, 240), "Backend FastAPI  (app/)", font=box_title, fill="#e8eef5")

    modules = [
        (450, 300, 650, 390, "Intent / routing", ["parse_message", "mémoire session", "scénarios région"]),
        (670, 300, 870, 390, "Services métier", ["obs_store", "special_store", "bms_store"]),
        (450, 420, 650, 510, "ChatbotService", ["reply()", "comparaisons", "suggestions"]),
        (670, 420, 870, 510, "API REST", ["POST /api/chat", "GET /api/dashboard", "GET /api/health"]),
    ]
    for x0, y0, x1, y1, head, lines in modules:
        rounded_box(draw, (x0, y0, x1, y1), "#1a3048", "#4a7fa0", 2, radius=10)
        draw.text((x0 + 12, y0 + 10), head, font=font(18, bold=True), fill="#9fd3ef")
        y = y0 + 42
        for line in lines:
            draw.text((x0 + 12, y), "• " + line, font=small, fill="#c9d7e6")
            y += 22

    # arrow data -> api
    arrow(draw, (300, 515), (418, 515), "#7ec8e6")
    draw.text((310, 482), "JSON / stores", font=tiny, fill="#8aa0b5")

    # --- Presentation layer ---
    ui_box = (1040, 220, 1520, 560)
    rounded_box(draw, ui_box, "#132437", "#9aebc4", 3)
    draw.text((1060, 240), "Interface web  (app/static/)", font=box_title, fill="#e8eef5")

    ui_parts = [
        (1070, 300, 1490, 370, "Console DRMNO", "Ticker OBS · cartes métriques · carte de vigilance"),
        (1070, 390, 1490, 460, "Chat conversationnel", "Questions FR · réponses structurées · badges vigilance"),
        (1070, 480, 1490, 540, "Interactions", "Pins carte · suggestions · mémoire multi-tours"),
    ]
    for x0, y0, x1, y1, head, body in ui_parts:
        rounded_box(draw, (x0, y0, x1, y1), "#1a3048", "#4f8f72", 2, radius=10)
        draw.text((x0 + 14, y0 + 12), head, font=font(18, bold=True), fill="#b7f0d0")
        draw.text((x0 + 14, y0 + 42), body, font=small, fill="#c9d7e6")

    arrow(draw, (900, 390), (1038, 390), "#9aebc4")
    draw.text((915, 358), "HTTP JSON", font=tiny, fill="#8aa0b5")

    # User bubble
    user_box = (1140, 620, 1420, 720)
    rounded_box(draw, user_box, "#1f6f9a", "#7ec8e6", 2)
    center_text(
        draw,
        user_box,
        ["Utilisateur", "Navigateur · http://127.0.0.1:8000"],
        [box_title, small],
        "#ffffff",
    )
    arrow(draw, (1280, 560), (1280, 618), "#9aebc4")
    draw.text((1290, 575), "question / clic carte", font=tiny, fill="#8aa0b5")

    # Bottom legend / flow summary
    legend = (60, 640, 1000, 900)
    rounded_box(draw, legend, "#101c2c", "#2a4058", 2)
    draw.text((80, 660), "Flux d’une requête (résumé)", font=box_title, fill="#7ec8e6")
    steps = [
        "1. L’utilisateur pose une question (ou clique une province sur la carte).",
        "2. FastAPI reçoit POST /api/chat et analyse l’intention (OBS / SPECIAL / BMS).",
        "3. Les stores locaux (JSON issus des PDF DRMNO) fournissent la donnée exacte.",
        "4. ChatbotService formate une réponse sourcée (paramètre demandé uniquement).",
        "5. L’interface affiche la réponse, les suggestions, et colore la vigilance.",
    ]
    y = 710
    for step in steps:
        draw.text((80, y), step, font=box_body, fill="#d5e2ef")
        y += 32

    # Footer note
    note = "Sources : bulletins officiels DRMNO / DGM — aucune donnée inventée"
    nw = draw.textbbox((0, 0), note, font=small)[2]
    draw.text(((W - nw) // 2, 930), note, font=small, fill="#6f8499")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PROJECT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    img.save(OUT_PROJECT, "PNG")
    print(OUT)
    print(OUT_PROJECT)


if __name__ == "__main__":
    main()
