"""Executive PDF: summary and concise evidence cards, based on reviewed records."""
from pathlib import Path
from xml.sax.saxutils import escape
from datetime import datetime, timezone, timedelta


PALETTE = {
    'seguimiento': ('#204F44', '#8DD7B6', 'Seguimiento'),
    'prioritaria': ('#594F2A', '#F0CA53', 'Inspección prioritaria'),
    'urgente': ('#582E38', '#EAA7B4', 'Alerta urgente'),
}


def build_pdf(target, result, rows, profile, created, types, store):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    width = A4[0] - 76
    ink, muted, line = '#19354D', '#5A7084', '#D6E2EA'
    styles = {
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor(ink), spaceAfter=7),
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor(muted), spaceAfter=5),
        'label': ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.HexColor(muted), spaceAfter=5),
        'h1': ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=21, leading=26, textColor=colors.HexColor(ink), spaceAfter=14),
        'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor(ink), spaceAfter=12),
        'teal': ParagraphStyle('teal', fontName='Helvetica', fontSize=12, leading=16, textColor=colors.HexColor('#00849A'), spaceAfter=12),
        'white': ParagraphStyle('white', fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=colors.white),
    }
    def text(value, style='body'):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style])
    def short(value, limit=650):
        value = ' '.join(str(value).split())
        return value if len(value) <= limit else value[:limit].rsplit(' ', 1)[0] + ' [...]'
    def field(label, value):
        return KeepTogether([text(label, 'label'), text(value), Spacer(1, 6)])
    def band(level, count=None):
        bg, accent, label = PALETTE[level]
        values = [[text(f'{count:02d}' if count is not None else 'NIVEL DE ATENCIÓN', 'white'), text(label, 'white')]]
        table = Table(values, colWidths=[width * .40, width * .60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg)),
            ('LINEBEFORE', (0, 0), (0, 0), 4, colors.HexColor(accent)),
            ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 13), ('BOTTOMPADDING', (0, 0), (-1, -1), 13),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return table
    months = [m['name'].replace('_', ' ') for m in result['months']]
    period = ' / '.join(months)
    project = profile['project']
    stamp = datetime.fromisoformat(created).astimezone(timezone(timedelta(hours=-5)))
    counts = {k: sum(r['level'] == k for r in rows) for k in PALETTE}
    pending = sum(not r['verified'] for r in rows)
    story = [Spacer(1, 20), text('INFORME EJECUTIVO\nDE INSPECCIÓN', 'h1'), text(project, 'teal'), text(period, 'h2'),
             text('Para revisión de jefatura | ' + stamp.strftime('%d/%m/%Y %H:%M') + ' (UTC-5)', 'small'), Spacer(1, 16),
             text('RESUMEN DE LA COMPARACIÓN', 'h2')]
    cards = Table([[
        [text('SISTEMA DE COORDENADAS', 'label'), text(result.get('crs', 'No registrado'), 'h2')],
        [text('TRAMO', 'label'), text(f"{result['start']:.2f} a {result['end']:.2f} m", 'h2')],
        [text('HALLAZGOS REVISADOS', 'label'), text(str(len(rows)), 'h2')],
    ]], colWidths=[width/3]*3)
    cards.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F1F6F9')), ('BOX',(0,0),(-1,-1),.6,colors.HexColor(line)), ('INNERGRID',(0,0),(-1,-1),.6,colors.HexColor(line)), ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),10), ('RIGHTPADDING',(0,0),(-1,-1),10), ('TOPPADDING',(0,0),(-1,-1),14), ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story += [cards, Spacer(1, 24), text('NIVELES DE ATENCIÓN', 'h2')]
    for level in PALETTE:
        story += [band(level, counts[level]), Spacer(1, 9)]
    story += [Spacer(1, 14), text('SÍNTESIS PARA JEFATURA', 'h2')]
    if rows:
        summary = f"Se registraron {len(rows)} hallazgos: {counts['urgente']} con alerta urgente, {counts['prioritaria']} para inspección prioritaria y {counts['seguimiento']} para seguimiento. {pending} pendientes de verificación de campo."
        action = ('Priorizar la revisión de los hallazgos marcados como urgentes y coordinar su atención con el responsable técnico.' if counts['urgente'] else
                  'Coordinar la comprobación en campo de los hallazgos prioritarios.' if counts['prioritaria'] else
                  'Mantener el seguimiento de los hallazgos registrados y contrastarlos en la próxima inspección.')
        reviewers = ', '.join(sorted({r['reviewer'] for r in rows}))
        story += [text(summary), text(action), text('Revisión registrada por: ' + short(reviewers, 200), 'small')]
    else:
        story += [text('No se han registrado hallazgos en esta comparación. La revisión está pendiente; este estado no certifica ausencia de daños o riesgo.')]
    story += [text('Los niveles de atención y las observaciones corresponden al revisor. Las diferencias de color entre imágenes no confirman daños ni sus causas.', 'small')]
    if result.get('warnings'):
        story += [text('Correspondencia geográfica: ' + short(' '.join(result['warnings']), 250), 'small')]
    order = {'urgente': 0, 'prioritaria': 1, 'seguimiento': 2}
    for finding in sorted(rows, key=lambda r: (order[r['level']], r['station'])):
        ref = next(r for r in result['references'] if abs(r['station'] - finding['station']) < .001)
        story += [PageBreak(), Spacer(1, 8), text(f"PROGRESIVA: {finding['station']:.2f} m", 'h1'),
                  text(types[finding['category']], 'teal'), band(finding['level']), Spacer(1, 16),
                  field('REVISOR / VERIFICACIÓN DE CAMPO', finding['reviewer'] + ' / ' + ('Registrada por el revisor' if finding['verified'] else 'Pendiente')),
                  field('OBSERVACIÓN', short(finding['evidence'])), field('JUSTIFICACIÓN DEL NIVEL DE ATENCIÓN', short(finding['rationale']))]
        cells = []
        for i, month in enumerate(months):
            video = ref['videos'][i] if i < len(ref.get('videos', [])) else {}
            ortho = ref['images'][i] if i < len(ref.get('images', [])) else {}
            source = video if video.get('url') else ortho
            content = [text(month, 'h2')]
            url = source.get('url', '')
            path = (store / url.removeprefix('/data/')).resolve()
            if url.startswith('/data/') and path.is_relative_to(store.resolve()) and path.is_file():
                image = Image(str(path))
                factor = min((width/2-8)/image.imageWidth, 165/image.imageHeight)
                image.drawWidth, image.drawHeight = image.imageWidth*factor, image.imageHeight*factor
                image.hAlign = 'LEFT'
                content.append(image)
                caption = f"Tiempo {video.get('time', 0):.2f} s. Progresiva proyectada {video.get('station', finding['station']):.2f} m." if video.get('url') else 'Ortofoto de referencia; sin fotograma cercano.'
                content += [Spacer(1, 5), text(caption, 'small')]
            else:
                content.append(text('Evidencia no disponible.', 'small'))
            cells.append(content)
        evidence = Table([cells], colWidths=[width/2]*2)
        evidence.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),8)]))
        story += [Spacer(1, 12), evidence, Spacer(1, 10), text('Las imágenes son evidencia de referencia. La ubicación del dron no delimita toda la superficie visible. El detalle completo se conserva en el registro de la aplicación.', 'small')]
    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(ink)); canvas.rect(0, A4[1]-5, A4[0], 5, fill=1, stroke=0)
        canvas.setFont('Helvetica-Bold', 10); canvas.drawString(38, A4[1]-30, 'HIDRO-VISION AI')
        canvas.setFont('Helvetica', 7); canvas.setFillColor(colors.HexColor(muted))
        canvas.drawRightString(A4[0]-38, A4[1]-30, short(period, 65))
        canvas.setStrokeColor(colors.HexColor(line)); canvas.line(38,A4[1]-40,A4[0]-38,A4[1]-40); canvas.line(38,42,A4[0]-38,42)
        canvas.drawString(38,28,'HIDRO-VISION AI | Revisión ejecutiva de jefatura'); canvas.drawRightString(A4[0]-38,28,str(doc.page))
        canvas.restoreState()
    SimpleDocTemplate(str(target), pagesize=A4, leftMargin=38, rightMargin=38, topMargin=56, bottomMargin=55,
                      title='HIDRO-VISION - Informe ejecutivo - '+project, author='HIDRO-VISION').build(story, onFirstPage=decorate, onLaterPages=decorate)
