"""One-page water-use report (PDF) built with ReportLab."""
import io
from datetime import datetime, timedelta

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Alert, SensorReading
from .services import field_savings

TEAL, SAND = colors.HexColor("#0C3B40"), colors.HexColor("#D8B77A")


def _moisture_chart(field, since):
    rows = list(SensorReading.objects.filter(field=field, recorded_at__gte=since).order_by("recorded_at")
                .values_list("recorded_at", "soil_moisture"))
    if len(rows) < 2:
        return None
    step = max(1, len(rows) // 120)
    pts = [(i, float(m)) for i, (_t, m) in enumerate(rows[::step])]
    d = Drawing(170 * mm, 55 * mm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 12 * mm, 8 * mm, 150 * mm, 42 * mm
    lp.data = [pts, [(pts[0][0], float(field.moisture_low)), (pts[-1][0], float(field.moisture_low))]]
    lp.lines[0].strokeColor, lp.lines[0].strokeWidth = TEAL, 1.4
    lp.lines[1].strokeColor, lp.lines[1].strokeDashArray = colors.HexColor("#B5472E"), (3, 2)
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, 60
    lp.xValueAxis.visible = False
    lp.yValueAxis.labels.fontSize = 7
    d.add(lp)
    return d


def build_pdf(fields, days):
    now = datetime.now()
    since = now - timedelta(days=days)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="AquaSense water report")
    st = getSampleStyleSheet()
    story = [Paragraph("AquaSense water-use report", st["Title"]),
             Paragraph("Period: last %d days, generated %s" % (days, now.strftime("%d %b %Y %H:%M")), st["Normal"]), Spacer(1, 8 * mm)]
    head = ["Field", "Crop", "Area (ha)", "Avg moisture", "Waterings", "Water used (L)", "Baseline (L)", "Saved"]
    rows, total_b, total_a = [head], 0, 0
    for f in fields:
        rs = [float(m) for m in SensorReading.objects.filter(field=f, recorded_at__gte=since).values_list("soil_moisture", flat=True)]
        sv = field_savings(f, days, now)
        n = f.schedules.filter(status="done", scheduled_for__gte=since).count()
        avg = "%.1f%%" % (sum(rs) / len(rs)) if rs else "n/a"
        if sv:
            total_b += sv["baseline_l"]; total_a += sv["actual_l"]
            rows.append([f.name, f.crop, "%.2f" % f.area_ha, avg, n, "{:,}".format(sv["actual_l"]), "{:,}".format(sv["baseline_l"]), "%s%%" % sv["saved_pct"]])
        else:
            rows.append([f.name, f.crop, "%.2f" % f.area_ha, avg, n, "n/a", "n/a", "n/a"])
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F4")]),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D6D3")), ("ALIGN", (2, 1), (-1, -1), "RIGHT")]))
    story += [t, Spacer(1, 6 * mm)]
    if total_b:
        saved = total_b - total_a
        story.append(Paragraph("Total: %s L used against an estimated %s L for a conventional fixed schedule, a difference of %s L (%.1f%%)." % (
            "{:,}".format(total_a), "{:,}".format(total_b), "{:,}".format(saved), saved / total_b * 100), st["Normal"]))
    alerts = Alert.objects.filter(field__in=fields, created_at__gte=since).count()
    story += [Spacer(1, 3 * mm), Paragraph("Alerts raised in this period: %d." % alerts, st["Normal"])]
    if len(fields) == 1:
        chart = _moisture_chart(fields[0], since)
        if chart:
            story += [Spacer(1, 6 * mm), Paragraph("Soil moisture (%%), dashed line is the watering threshold (%s%%)" % fields[0].moisture_low, st["Heading4"]), chart]
    story += [Spacer(1, 6 * mm), Paragraph("The baseline is an estimate of a conventional fixed drip schedule and is not a measurement.", st["Italic"])]
    doc.build(story)
    return buf.getvalue()
