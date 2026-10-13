"""Code-rendered layouts for conspicuously unofficial fictional study documents."""

import random

from document_generator import Canvas, DISCLAIMER_HEIGHT, INK, MUTED, RED, SIZES, fee_rows, money

LINE = "#D8DCE2"
PANEL = "#F5F7FA"
NAVY = "#253746"
GREEN = "#27564B"


def schedule_slots():
    return [
        ("CMSC 105", "6380", "Tuesday and Thursday", "1:00 PM", "2:15 PM", "Online", "Dr. J. Smith"),
        ("STAT 200", "9040", "Monday", "6:00 PM", "8:30 PM", "Online", "Prof. A. Davis"),
    ]


def _topbar(c, title, subtitle):
    w, _ = c.image.size
    c.box((0, 0, w, 96), NAVY)
    c.box((0, 96, w, 104), RED)
    c.text("UMGC INDEPENDENT DESIGN PROTOTYPE", (54, 24, 640, 34), 21, "white", True)
    c.text("FICTIONAL DOCUMENT SET / NOT FOR VERIFICATION", (w - 680, 26, 620, 30), 17, "#DDE5EC", True, "right")
    c.text(title, (54, 138, w - 108, 64), 46, INK, True)
    c.text(subtitle, (54, 206, w - 108, 36), 22, MUTED)


def _field(c, label, value, x, y, width, value_size=24):
    c.text(label.upper(), (x, y, width, 25), 15, MUTED, True)
    c.text(value, (x, y + 28, width, 58), value_size, INK, True)


def _table_header(c, y, columns, left=54, right=1546, height=48):
    c.box((left, y, right, y + height), NAVY)
    for label, x, width in columns:
        c.text(label, (x, y + 14, width, 24), 15, "white", True)


def render_code_v2(kind, profile, data, assets, seed):
    if kind == "schedule":
        return render_code_schedule(profile, data, assets, seed)
    if kind == "student_card":
        return render_code_card(profile, data, assets, seed)
    if kind == "receipt":
        return render_code_receipt(profile, data, assets, seed)
    raise ValueError("Unknown document type.")


def render_code_schedule(profile, data, assets, seed):
    c = Canvas(SIZES["schedule"])
    session = data["session"]
    _topbar(c, "Course Schedule", "Proposed class schedule generated from verified public course and calendar facts.")
    _field(c, "Fictional student", profile["full_name"], 54, 278, 600)
    _field(c, "Prototype ID", profile["student_id"], 720, 278, 330)
    _field(c, "Term", session["term"], 1110, 278, 420)
    _field(c, "Session", f"{session['start']} to {session['end']}", 54, 378, 520)
    _field(c, "Academic level", "Undergraduate", 640, 378, 330)
    _field(c, "Status", "Proposed only", 1040, 378, 360)
    c.box((54, 492, 1546, 548), PANEL)
    c.text("This is a code-rendered planning record. It does not establish current enrollment.",
           (76, 509, 1450, 28), 20, RED, True)
    columns = [
        ("COURSE", 76, 120), ("DESCRIPTION", 210, 420), ("SECTION", 654, 100),
        ("CREDITS", 772, 95), ("DAYS", 894, 190), ("TIME", 1102, 185),
        ("LOCATION", 1305, 104), ("INSTRUCTOR", 1422, 110),
    ]
    _table_header(c, 590, columns)
    slots = schedule_slots()
    courses = {course["code"]: course for course in data["courses"]}
    for i, (code, section, days, start, end, location, instructor) in enumerate(slots):
        y = 638 + i * 124
        c.box((54, y, 1546, y + 123), "#FFFFFF" if i % 2 == 0 else "#F9FAFB")
        c.draw.line((54, y + 123, 1546, y + 123), fill=LINE, width=2)
        course = courses.get(code, {"title": code, "credits": ""})
        values = [
            (code, 76, 120, 23, True), (course["title"], 210, 420, 22, False),
            (section, 654, 100, 21, False), (str(course["credits"]), 772, 95, 21, False),
            (days, 894, 190, 20, False), (f"{start} - {end}", 1102, 185, 20, False),
            (location, 1305, 104, 20, False), (instructor, 1422, 110, 18, False),
        ]
        for value, x, width, size, bold in values:
            c.text(value, (x, y + 34, width, 58), size, INK, bold)
    c.text("Schedule time blocks, sections and instructors are fictional planning fields. Verify real registration in the school portal.",
           (54, 912, 1492, 40), 20, MUTED)
    c.text("Public facts used: Fall 2026 Undergraduate 8-Wk Session 3; CMSC 105 and STAT 200 course titles and credits.",
           (54, 960, 1492, 40), 19, MUTED)
    c.disclaimer("schedule", c.image.height - DISCLAIMER_HEIGHT)
    return c


def render_code_card(profile, data, assets, seed):
    c = Canvas(SIZES["student_card"])
    session = data["session"]
    _topbar(c, "Student Card", "Design prototype with a fictional person and code-rendered fields.")
    c.box((72, 296, 1528, 814), "#F9FAFB")
    c.box((72, 296, 1528, 354), NAVY)
    c.text("STUDENT CARD DESIGN PROTOTYPE", (100, 314, 700, 28), 20, "white", True)
    c.text("NOT VALID FOR IDENTIFICATION", (950, 314, 550, 28), 20, "#F1D6DC", True, "right")
    c.image_at(assets["portrait"], (112, 396, 330, 330))
    c.text("FICTIONAL PERSON", (112, 744, 330, 34), 18, RED, True)
    _field(c, "Name", profile["full_name"], 500, 398, 760, 34)
    _field(c, "Prototype ID", profile["student_id"], 500, 510, 330, 30)
    _field(c, "Date of birth", profile["date_of_birth"], 890, 510, 260, 30)
    _field(c, "Country", profile["country"], 1200, 510, 250, 30)
    c.text(data["program"] + " / Undergraduate", (500, 636, 900, 48), 27, INK, True)
    c.text("Prototype validity: " + session["start"] + " to " + session["end"],
           (500, 705, 900, 44), 24, INK, True)
    c.text("Validity dates mirror the selected academic session and do not represent an issued credential.",
           (500, 758, 900, 34), 18, MUTED)
    c.text("No barcode, signature, seal or authentication feature is included.", (72, 856, 1456, 34), 19, MUTED)
    c.disclaimer("student_card", c.image.height - DISCLAIMER_HEIGHT)
    return c


def render_code_receipt(profile, data, assets, seed):
    c = Canvas(SIZES["receipt"])
    session = data["session"]
    _topbar(c, "Tuition Estimate", "Code-rendered cost worksheet. No payment or balance settlement is represented.")
    _field(c, "Fictional student", profile["full_name"], 54, 292, 620)
    _field(c, "Prototype ID", profile["student_id"], 724, 292, 420)
    _field(c, "Term", session["term"], 54, 400, 360)
    _field(c, "Session dates", f"{session['start']} to {session['end']}", 468, 400, 520)
    c.box((54, 524, 1221, 594), PANEL)
    c.text("ESTIMATE ONLY / NOT PROOF OF PAYMENT", (78, 544, 830, 32), 24, RED, True)
    c.text("Amounts are calculated from public-rate assumptions.", (78, 574, 830, 24), 16, MUTED)
    columns = [("DESCRIPTION", 78, 450), ("CREDITS", 552, 120), ("RATE", 704, 160), ("AMOUNT", 948, 240)]
    _table_header(c, 654, columns, left=54, right=1221, height=50)
    rows, total = fee_rows(data)
    y = 704
    for i, row in enumerate(rows):
        c.box((54, y, 1221, y + 112), "#FFFFFF" if i % 2 == 0 else "#F9FAFB")
        c.draw.line((54, y + 112, 1221, y + 112), fill=LINE, width=2)
        c.text(row["description"], (78, y + 34, 450, 48), 23, INK, True)
        c.text(row["credits"], (552, y + 34, 120, 48), 23)
        c.text(money(row["rate"]) if row["rate"] is not None else "N/A", (704, y + 34, 160, 48), 23)
        c.text(money(row["amount"]) if row["amount"] is not None else "N/A", (948, y + 34, 240, 48), 23, INK, True, "right")
        y += 112
    c.box((54, y + 24, 1221, y + 106), NAVY)
    c.text("ESTIMATED TOTAL (USD)", (78, y + 48, 600, 40), 25, "white", True)
    c.text(money(total) if total is not None else "N/A", (882, y + 42, 306, 48), 31, "white", True, "right")
    c.text("Cost basis: out-of-state standard undergraduate rate; six proposed credits; technology fee included.",
           (54, y + 150, 1167, 72), 22, MUTED)
    c.text("No transaction ID, paid stamp, balance, official seal or receipt authentication is included.",
           (54, y + 232, 1167, 72), 22, RED, True)
    c.text("Public rates checked " + data["verified_on"] + ". Rates, fees, discounts and materials may change.",
           (54, 1462, 1167, 54), 20, MUTED)
    c.disclaimer("receipt", c.image.height - DISCLAIMER_HEIGHT)
    return c


def render_variant(kind, profile, data, assets, seed):
    rng = random.Random(str(seed) + kind)
    c = Canvas(SIZES[kind])
    w, h = c.image.size
    margin = rng.randrange(64, 96)
    width = w - 2 * margin
    variant = rng.randrange(3)
    accent = rng.choice([RED, "#27564B", "#414148"])
    title = {"schedule": "Course Schedule", "receipt": "Tuition Estimate", "student_card": "Student Card"}[kind]
    c.text("INDEPENDENT DESIGN PROTOTYPE / UMGC", (margin, 34, width, 40), 22, RED, True)
    if variant == 0:
        c.box((margin, 91, margin + 8, 233), accent)
        c.text(title, (margin + 30, 94, width - 30, 74), rng.randrange(46, 57), INK, True)
        c.text("University of Maryland Global Campus", (margin + 30, 186, width - 30, 44), 26)
    else:
        c.text("University of Maryland Global Campus", (margin, 97, width, 44), 27, INK, True)
        c.text(title, (margin, 161, width, 76), rng.randrange(43, 55), INK, True,
               "right" if variant == 2 else "left")
        c.box((margin, 256, w - margin, 259), accent)
    session = data["session"]
    c.text(session["term"] + " / " + session["name"], (margin, 280, width, 42), 24, MUTED)
    c.text(f"{session['start']} to {session['end']}", (margin, 331, width, 42), 24)
    y = 400 + rng.randrange(0, 22)
    if kind == "student_card":
        portrait_right = variant != 0
        px = w - margin - 320 if portrait_right else margin
        tx = margin if portrait_right else margin + 360
        tw = width - 370
        c.image_at(assets["portrait"], (px, y, 320, 335))
        c.text("FICTIONAL PERSON", (px, y + 355, 320, 40), 20, RED, True)
        c.label("Fictional student", profile["full_name"], tx, y, tw)
        c.label("Prototype ID", profile["student_id"], tx, y + 128, tw)
        c.text(profile["country"] + " / Born " + profile["date_of_birth"], (tx, y + 260, tw, 80), 25)
        c.text("PROTOTYPE VALIDITY: " + session["start"] + " to " + session["end"],
               (margin, 834, width, 50), 27, INK, True)
    else:
        if variant == 1:
            c.label("Prototype ID", profile["student_id"], margin, y, int(width * .40))
            c.label("Fictional student", profile["full_name"], margin + int(width * .43), y, int(width * .57))
        else:
            c.label("Fictional student", profile["full_name"], margin, y, int(width * .60))
            c.label("Prototype ID", profile["student_id"], margin + int(width * .65), y, int(width * .35))
        y += 148
        if kind == "schedule":
            c.text("PROPOSED WEEKLY TIME BLOCKS / NOT A REGISTRATION RECORD", (margin, y, width, 40), 23, RED, True)
            y += 61
            slots = [
                ("Monday and Wednesday", "10:00 AM", "11:15 AM"),
                ("Tuesday and Thursday", "1:00 PM", "2:15 PM"),
                ("Monday", "6:00 PM", "8:30 PM"),
                ("Wednesday", "3:00 PM", "5:30 PM"),
            ]
            for index, course in enumerate(data["courses"]):
                days, start, end = slots[(index + variant) % len(slots)]
                c.box((margin, y, w - margin, y + 2), "#A5A5A5")
                if variant == 2:
                    c.text(course["code"] + " / " + course["title"], (margin, y + 17, width, 66), 28, INK, True)
                    c.text(f"{days}  |  {start} - {end}", (margin, y + 84, width, 40), 23, INK, True)
                    c.text(f"{course['credits']} credits / Online session / Proposed time block",
                           (margin, y + 127, width, 40), 22, MUTED)
                else:
                    c.text(course["code"], (margin, y + 20, 210, 66), 27, INK, True)
                    c.text(course["title"], (margin + 230, y + 20, width - 470, 76), 27)
                    c.text(f"{course['credits']} credits\n{days}", (w - margin - 205, y + 20, 205, 80), 22)
                    c.text(f"{start} - {end} / Online", (margin + 230, y + 92, width - 470, 40), 22, MUTED)
                y += 175
            c.text("Time blocks are fictional planning data. Actual section times and availability have not been verified.",
                   (margin, 941, width, 64), 22, MUTED)
        else:
            c.text("FICTIONAL COST ESTIMATE / NO PAYMENT RECORDED", (margin, y, width, 60), 25, RED, True)
            y += 94
            rows, total = fee_rows(data)
            for row in rows:
                c.box((margin, y, w - margin, y + 2), "#A5A5A5")
                c.text(row["description"], (margin, y + 24, int(width * .63), 64), 29, INK, True)
                c.text(money(row["amount"]) if row["amount"] is not None else "",
                       (margin + int(width * .68), y + 24, int(width * .32), 60), 30, INK, True, "right")
                c.text(f"{row['credits']} credits x {money(row['rate'])}" if row["rate"] is not None else "Rate unavailable",
                       (margin, y + 99, width, 50), 25, MUTED)
                y += 193 if variant == 0 else 174
            c.box((margin, y + 12, w - margin, y + 16), accent)
            c.text("ESTIMATED TOTAL (USD)", (margin, y + 51, int(width * .64), 64), 28, INK, True)
            c.text(money(total) if total is not None else "", (margin + int(width * .68), y + 46, int(width * .32), 72), 36, INK, True, "right")
            c.text("Out-of-state undergraduate rate. No payment or balance settlement is represented.",
                   (margin, 1320, width, 95), 25, RED, True)
            c.text("Public rates checked " + data["verified_on"] + ". Other fees and discounts are not included.",
                   (margin, 1447, width, 90), 23, MUTED)
    c.disclaimer(kind, h - DISCLAIMER_HEIGHT)
    return c
