import math
import io
from datetime import datetime

from django.db import connections,IntegrityError,transaction
from django.template.defaultfilters import length
from reportlab.lib.styles import getSampleStyleSheet

from .models import (OrdenCompraStarsoft, Proveedor,OrdenCompraDespacho, Empresa, OrdenCompra, Producto, ProveedorTransporte, Transportista,
    Despacho, DetalleDespacho, ConfiguracionDespacho)
from .forms import BaseDatosForm
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber
import json
from .utils import renderizar_template,convertir_html_a_pdf,procesar_data_reporte
import os
import tempfile
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.colors import Color

def get_db_connection(base_datos):
    connection = connections[base_datos]  # Usa la base de datos dinámica
    return connection

def extract_pdf_tables(file):
    with pdfplumber.open(file) as pdf:
        tables = []

        # Intentar extraer tablas de cada página del PDF
        for i, page in enumerate(pdf.pages):
            table = page.extract_table()

            if table:
                print(f"Tabla extraída en página {i + 1}:")
                headers = table[0]  # La primera fila contiene los encabezados
                table_data = [headers]  # Agregar los encabezados como la primera fila

                for row in table[1:]:
                    table_data.append(row)  # Agregar las filas de datos

                tables.append(table_data)
            else:
                print(f"No se encontró una tabla en la página {i + 1}")

        # Si no se extrajeron tablas, intentamos extraer texto y convertirlo
        if not tables:
            print("No se encontraron tablas, pero aquí está el texto extraído:")
            text = ""
            for page in pdf.pages:
                text += page.extract_text()  # Extraer todo el texto del PDF

            #print(text)
            lines = text.splitlines()  # Dividir el texto en líneas

            data = []
            header_found = False

            # Encabezado ajustado según la estructura del texto
            header = ["No.","NRO CE", "FECHA", "PLACA", "TRANSPORTISTA", "BULTOS", "PESO BRUTO", "PESO NETO",
                      "Nros. Precintos SENASAG"]

            for line in lines:
                # Detectar si la línea es parte de la tabla (empieza con el encabezado)
                if line.startswith("No.") and not header_found:
                    header_found = True  # Marca que el encabezado ha sido encontrado
                elif header_found:
                    # Si encontramos la línea "TOTALES", detenemos la extracción sin agregar la línea
                    if "TOTALES" in line:
                        break
                    else:
                        # Separar las columnas por espacios
                        columns = line.split()

                        # Asegurarnos de tener al menos las 8 columnas esperadas antes de procesar
                        if len(columns) >= len(header):
                            # Organizar las columnas fijas
                            no = columns[0]  # No.
                            nro_ce = columns[1]  # NRO CE
                            fecha = columns[2]  # FECHA
                            placa = columns[3]  # PLACA

                            # Las últimas 4 columnas son siempre los mismos datos
                            bultos = columns[-4]
                            peso_bruto = columns[-3]
                            peso_neto = columns[-2]
                            nro_precintos = columns[-1]

                            # Todo lo que queda en el medio se considera como el nombre del transportista
                            transportista = " ".join(columns[4:-4])

                            # Crear la fila de datos organizada
                            row = [no, nro_ce, fecha, placa, transportista, bultos, peso_bruto, peso_neto,
                                   nro_precintos]
                            data.append(row)
            #print("encontro encabezado?", header_found)
            # Crear un DataFrame con los datos extraídos
            df_text_table = pd.DataFrame(data, columns=header)
            # Convertir el DataFrame a una lista de diccionarios
            return df_text_table.to_dict(orient='records')

# Función para extraer datos de un archivo Excel
def extract_excel_data(file):
    try:
        df = pd.read_excel(file, sheet_name=None)
        data = {}
        for sheet_name, sheet_data in df.items():
            data[sheet_name] = sheet_data.to_dict(orient='records')  # Convertir a lista de diccionarios
        return data
    except Exception as e:
        return {"error": str(e)}

# Función para extraer texto de una imagen usando Tesseract
def extract_image_text(file):
    img = Image.open(file)
    text = pytesseract.image_to_string(img)
    return text

# Vista para subir y procesar archivo
@api_view(['POST'])
def upload_file(request):
    if 'file' in request.FILES:
        file = request.FILES['file']
        file_type = file.name.split('.')[-1].lower()

        try:
            if file_type == 'pdf':
                tables = extract_pdf_tables(file)
                response_data = {"tables": tables}
            elif file_type in ['xls', 'xlsx']:
                data = extract_excel_data(file)
                response_data = {"data": data}
            elif file_type in ['jpg', 'jpeg', 'png']:
                text = extract_image_text(file)
                response_data = {"text": text}
            else:
                response_data = {'message': 'Formato de archivo no soportado'}

            return JsonResponse({'status': 'success', 'data': response_data}, status=200)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({"error": "No se proporcionó archivo."}, status=400)

leyenda_codigos = {
    1: "Transbordo",
    2: "Pago estiba",
    3: "No pago estiba",
    4: "Pago parcial",
}

@api_view(['POST'])
def upload_file_excel(request):
    try:
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({"error": "No se proporcionó archivo."}, status=400)

        # Leer el archivo Excel usando openpyxl
        df = pd.read_excel(uploaded_file, engine='openpyxl', skiprows=1, header=0)

        # Limpiar y renombrar columnas
        df.columns = ["Item", "PLACA", "sacos_cargados", "peso_cargado", "PLACA_Balanza",
                      "sacos_entregados", "peso_balanza", "Merma", "descuentos_faltantes",
                      "descuentos_rotos", "descuentos_humedos", "descuentos_mojados", "Status_pago"]

        # Renombrar columnas para el frontend
        df.rename(columns={
            "Item": "item_nombre",
            "PLACA": "placa_salida",
            "sacos_cargados": "sacos_cargados",
            "peso_cargado": "peso_salida",
            "PLACA_Balanza": "placa_llegada",
            "sacos_entregados": "sacos_descargados",
            "peso_balanza": "peso_llegada",
            "Merma": "merma",
            "descuentos_faltantes": "sacos_faltantes",
            "descuentos_rotos": "sacos_rotos",
            "descuentos_humedos": "sacos_humedos",
            "descuentos_mojados": "sacos_mojados",
            "Status_pago": "descripcion_pago"
        }, inplace=True)



        # Procesar códigos usando la leyenda
        def procesar_codigo(codigo):
            try:
                codigo_entero = int(math.floor(float(codigo)))
                return leyenda_codigos.get(codigo_entero, "Seleccione")
            except (ValueError, TypeError):
                return "Seleccione"

        # Aplicar procesamiento de códigos
        df["pago_estiba"] = df["descripcion_pago"].apply(procesar_codigo)

        # Borrar columnas que no necesito
        df.drop(columns=["item_nombre", "merma","descripcion_pago"], inplace=True)

        # Convertir el DataFrame en una respuesta JSON
        result = df.to_dict(orient='records')

        return JsonResponse({"data": result}, status=200)

    except Exception as e:
        return JsonResponse({"error": f"Error al procesar archivo: {str(e)}"}, status=400)

@csrf_exempt
def listar_importaciones(request):
    form = BaseDatosForm(request.POST or None)
    registros = None

    if request.method == 'POST' and form.is_valid():
        base_datos = form.cleaned_data['base_datos']
        registros = OrdenCompraStarsoft.objects.using(base_datos).all()  # Consultar en la base seleccionada

    return render(request, 'importaciones/lista_importaciones.html', {'form': form, 'registros': registros})

@csrf_exempt
def buscar_orden_importacion(request):
    base_datos = request.GET.get('base_datos', 'default')  # Obtén el parámetro base_datos desde la URL
    query = request.GET.get('query', '')  # El término de búsqueda (CNUMERO)

    # Verifica que los parámetros sean válidos
    if base_datos and query:
        try:
            # Obtener la conexión a la base de datos
            connection = get_db_connection(base_datos)

            # Realizar la consulta a la base de datos
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT TOP 5 
                        i.CNUMERO,
                        i.CDESARTIC,
                        i.CCODARTIC,
                        i.NCANTIDAD,
                        i.CUNIDAD,
                        i.NPREUNITA,
                        i.NTOTVENT,
                        o.CDESPROVE,
                        o.CCODPROVE
                    FROM IMPORD i
                    INNER JOIN IMPORC o ON i.CNUMERO = o.CNUMERO
                    WHERE i.CNUMERO LIKE %s
                """, [f'%{query}%'])
                resultados = cursor.fetchall()

            # Serializar los resultados
            resultado_serializado = []

            for row in resultados:

                orden = {
                    'numero_oc': row[0],  # Asegúrate de que el índice coincida con el esquema de tu tabla
                    'producto': row[1],  # Este es solo un ejemplo, ajusta según las columnas
                    'codigo_producto': row[2],
                    'cantidad': row[3],
                    'unidad_medida': row[4],
                    'precio_unitario': row[5],
                    'precio_total': row[6],
                    'proveedor': row[7],  # Ajusta según la columna correcta
                    'codprovee': row[8],  # Ajusta según la columna correcta
                }
                resultado_serializado.append(orden)

            # Retornar los resultados en formato JSON
            return JsonResponse(resultado_serializado, safe=False, status=200)

        except ValueError as e:
            # Si hay un error con la base de datos
            return JsonResponse({'error': str(e)}, status=500)

        except Exception as e:
            # Manejo de errores generales
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

@csrf_exempt
def buscar_proveedor(request):
    if request.method == 'GET':
        base_datos = request.GET.get('base_datos')  # Base de datos seleccionada
        termino_busqueda = request.GET.get('query')  # Término de búsqueda

        # Valida que se haya proporcionado la base de datos y el término de búsqueda
        if base_datos and termino_busqueda:
            # Filtra las órdenes que coincidan con el término de búsqueda
            registros = Proveedor.objects.using(base_datos).filter(
                PRVCNOMBRE__icontains=termino_busqueda
            )[:5]  # Carga los detalles relacionados

            # Serializa las órdenes junto con sus detalles
            resultado = []
            for registro in registros:
                # Extraemos la orden principal
                proveedor = {
                    'nombre': registro.PRVCNOMBRE,
                }

                #print(proveedor)
                resultado.append(proveedor)

            return JsonResponse(resultado, safe=False, status=200)
        else:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

def generar_reporte_dos(request):
    if request.method == 'POST':
        try:
            # Datos para el reporte
            data = json.loads(request.body)

            data_procesada=procesar_data_reporte(data)
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'importaciones/reporteFletesExtranjeros.html')

            # Renderizar el HTML
            html_content = renderizar_template(template_path, data_procesada)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                # Llama a la función para convertir el HTML a PDF y guardarlo en el archivo temporal
                convertir_html_a_pdf(html_content, temp_pdf.name)

                # Abre el archivo temporal para enviarlo como respuesta HTTP
                temp_pdf.seek(0)  # Asegúrate de que el puntero esté al principio del archivo
                response = HttpResponse(temp_pdf.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="reporte.pdf"'

                # Después de enviar el archivo, el archivo temporal se elimina automáticamente cuando termine
                return response
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Error al procesar JSON'}, status=400)
    else:
            return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

def generar_reporte_tres(request):
    if request.method == 'POST':
        try:
            # Datos para el reporte
            data = json.loads(request.body)

            data_procesada=procesar_data_reporte(data)
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'importaciones/reporteFleteExtranjeroDetallado.html')

            # Renderizar el HTML
            html_content = renderizar_template(template_path, data_procesada)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                # Llama a la función para convertir el HTML a PDF y guardarlo en el archivo temporal
                convertir_html_a_pdf(html_content, temp_pdf.name)

                # Abre el archivo temporal para enviarlo como respuesta HTTP
                temp_pdf.seek(0)  # Asegúrate de que el puntero esté al principio del archivo
                response = HttpResponse(temp_pdf.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="reporte.pdf"'

                # Después de enviar el archivo, el archivo temporal se elimina automáticamente cuando termine
                return response
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Error al procesar JSON'}, status=400)
    else:
            return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

def generar_reporte_base(request):
    data_unprocess = json.loads(request.body)
    data = procesar_data_reporte(data_unprocess)
    buffer = io.BytesIO()

    # Crear un archivo PDF
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    c.setTitle(" Reporte cálculo de flete")


    # Obtener las dimensiones de la página
    width, height = landscape(A4)



    # primera linea
    c.setFont("Helvetica", 10)
    current_y = height - 40
    c.drawString(40, current_y, f"{data['procesado']['empresa']}")

    current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.setFont("Helvetica",7)
    c.drawString(width-130, current_y, f"{current_datetime}")

    #segunda linea
    c.setFont("Helvetica-Bold", 10)
    texto = f"{data['dataForm']['producto']}"
    text_width = c.stringWidth(texto, "Helvetica", 12)
    # Calcular la posición X para centrar el texto
    x_position = (width - text_width) / 2 + 20
    # Dibujar el texto centrado
    current_y-=20
    c.drawString(x_position, current_y, texto)

    # tercera linea
    current_y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, current_y, f"CARTA PORTE: {data['dataForm']['cartaPorte']}")



    # CUARTA LINEA DATOS DEL DESPACHO
    ordenes_recojo = data['dataForm']['ordenRecojo']
    ordenes_string = " / ".join([f"{row['oc']['numero_oc']}({row['numeroRecojo']})" for row in ordenes_recojo])
    textos = [
        f"N° DUA: {data['dataForm']['dua']}",
        f"Fec. Num.: {data['procesado']['fecha_numeracion']}",
        f"Factura N°: {data['dataForm']['numFactura']}",
        f"OC: {ordenes_string}",
        f"CANT. {data['procesado']['total_sacos_cargados']} sacos",
        f" {data['dataForm']['pesoNetoCrt']} kg"
    ]
    # Fuente y tamaño
    font_name = "Helvetica"
    font_size = 8
    c.setFont(font_name, font_size)
    # Espacio entre columnas
    margin = 30
    # Posición inicial en Y (mantener fija)
    current_y -= 20
    y_position = current_y
    # Posición inicial en X
    x_position = 40
    # Dibujar todos los textos en una línea tomando en cuenta su tamaño para darle cierto espaciado
    for texto in textos:
        # Calcular el ancho de cada texto
        text_width = c.stringWidth(texto, font_name, font_size)

        # Dibujar el texto
        c.drawString(x_position, y_position, texto)

        # Actualizar la posición X para el siguiente texto
        x_position += text_width + margin

        # Si el texto excede el tamaño de la página en el eje X, detener la creación del contenido
        if x_position > width:
            break



    #QUINTA LINEA DONDE INICIA LA TABLA:
    current_y -= 20
    # Datos iniciales de la tabla #1 (Titulos y subtitulos)
    data_table = [
        # Línea de títulos
        ['FEC. INGRE.', 'EMPRESA DE TRANSP.', 'CARGA', '', '', '', 'DESCARGA', '', '','', 'DESCUENTOS', '', '', '', ''],
        ['', '', 'N°', 'Placa S.', 'Sacos C.', 'Peso S.', 'Placa L.', 'Sacos D.', 'Peso L.', 'Merma', 'S. Falt.',
         'S. Rotos', 'S. Humed.', 'S. Mojad.','Estibaje'],
    ]
    styles = getSampleStyleSheet()
    parrafo = Paragraph(f"<para align=center spaceb=3><b>{data['dataForm']['transportista']}</b></para>",
                        styles["BodyText"])
    for i, row in enumerate(data['dataTable']):
        if i == 0:  # Primera fila (datos especiales)
            data_table.append([
                f"{data['procesado']['fecha_numeracion']}",
                parrafo,
                str(row['numero']),
                row['placa'],
                str(row['sacosCargados']),
                str(row['pesoSalida']),
                row['placaLlegada'],
                str(row['sacosDescargados']),
                str(row['pesoLlegada']),
                str(row['merma']),
                str(row['sacosFaltantes']),
                str(row['sacosRotos']),
                str(row['sacosHumedos']),
                str(row['sacosMojados']),
                str(row['pagoEstiba']),
            ])
        else:  # Para el resto de las filas
            data_table.append([
                "",  # Cadena vacía
                "",  # Cadena vacía
                str(row['numero']),
                row['placa'],
                str(row['sacosCargados']),
                str(row['pesoSalida']),
                row['placaLlegada'],
                str(row['sacosDescargados']),
                str(row['pesoLlegada']),
                str(row['merma']),
                str(row['sacosFaltantes']),
                str(row['sacosRotos']),
                str(row['sacosHumedos']),
                str(row['sacosMojados']),
                str(row['pagoEstiba']),
            ])
    # Agregamos fila de totales
    data_table.append(
        ['', f"Flete x TM: $ {data['dataForm']['fletePactado']:.2f}", f"{data['procesado']['len_tabla']}", 'TOTAL',
         f"{data['procesado']['total_sacos_cargados']}", f"{data['procesado']['suma_peso_salida']}", 'TOTAL',
         f"{data['procesado']['total_sacos_descargados']}", f"{data['procesado']['suma_peso_llegada']}",
         f"{data['procesado']['merma_total']}", f"{data['procesado']['total_sacos_faltantes']}",
         f"{data['procesado']['total_sacos_rotos']}", f"{data['procesado']['total_sacos_humedos']}",
         f"{data['procesado']['total_sacos_mojados']}"])
    # Ancho de columnas
    col_widths = [60, 110, 20, 60, 40, 60, 60, 60, 40, 60, 30, 30, 30, 30, 70]
    # Crear la tabla
    table = Table(data_table, colWidths=col_widths, rowHeights=15)
    color_rosa = Color(red=250 / 255, green=210 / 255, blue=202 / 255)
    color_celeste = Color(red=176 / 255, green=225 / 255, blue=250 / 255)
    numero_filas = len(data_table)
    # Estilos para la tabla
    table_style = TableStyle([
        ('SPAN', (0, 0), (0, 1)),  # Fusionar "FEC. INGRE."
        ('SPAN', (1, 0), (1, 1)),  # Fusionar "EMPRESA DE TRANSP."
        ('SPAN', (2, 0), (5, 0)),  # Fusionar "CARGA"
        ('SPAN', (6, 0), (9, 0)),  # Fusionar "DESCARGA"
        ('SPAN', (10, 0), (14, 0)),  # Fusionar "DESCUENTOS"
        ('SPAN', (0, 2), (0, numero_filas - 1)),  # Fusionar "fecha"
        ('SPAN', (1, 2), (1, numero_filas - 2)),  # Fusionar "nombre empresa transporte"
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centrar todo
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Fondo gris para los títulos
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),  # Fondo gris claro para subtítulos
        ('BACKGROUND', (2, 0), (5, numero_filas), colors.yellowgreen),  # Color "CARGA"
        ('BACKGROUND', (6, 0), (9, numero_filas),color_celeste),  # Color "DESCARGA"
        ('BACKGROUND', (10, 0), (14, numero_filas),color_rosa),  # Fusionar "DESCUENTOS"
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Negrita en títulos
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),  # Negrita en subtítulos
        #('FONTSIZE', (15, 0), (15, numero_filas - 1), 5),
    ])
    # Aplicar estilos a la tabla
    table.setStyle(table_style)
    # Calcular la altura total de la tabla
    table_height = len(data_table) * 15 # 20 es la altura de cada fila
    # Calcular la posición de la tabla en la página
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, current_y - table_height )  # Ajustar la posición dependiendo de la cantidad de filas

    current_y= current_y - table_height - 20

    # Data para la tabla #2 (Detalles de pesos)
    second_data_table=[
        ["Faltante peso Sta. Cruz - Desaguadero:",f"{data['procesado']['diferencia_de_peso']:.2f} Kg."],
        ["Merma permitida:",f"{data['dataExtra']['mermaPermitida']:.2f} Kg."],
        ["Desc. diferencia de peso:",f"{data['procesado']['diferencia_peso_por_cobrar']:.2f} Kg."],
        ["Desc. sacos falantes:",f"{data['procesado']['descuento_peso_sacos_faltantes']:.2f} Kg."]
    ]
    second_col_widths=[110,50]
    second_table = Table(second_data_table, colWidths=second_col_widths,rowHeights=14)
    second_table_style=TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Centrar
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    second_table.setStyle(second_table_style)
    second_table_height = len(second_data_table) * 14
    second_table.wrapOn(c, width, height)
    second_table.drawOn(c, 40,current_y - second_table_height )


    #Data para la tabla #3 (Resumen de descuentos)
    third_data_table=[
        ["FLETE",f"$ {data["procesado"]["flete_base"]:.2f}"],
        ["Dscto. por dif. de peso", f"$ {data["procesado"]["descuento_por_diferencia_peso"]:.2f}"],
        ["Dscto. por sacos faltantes", f"$ {data["procesado"]["descuento_sacos_faltantes"]:.2f}"],
        ["Dscto. por sacos rotos", f"$ {data["procesado"]["descuento_sacos_rotos"]:.2f}"],
        ["Dscto. por sacos humedos", f"$ {data["procesado"]["descuento_sacos_humedos"]:.2f}"],
        ["Dscto. por sacos mojados", f"$ {data["procesado"]["descuento_sacos_mojados"]:.2f}"],
        ["FLETE TOTAL", f"$ {data["procesado"]["total_luego_dsctos_sacos"]:.2f}"],
    ]
    #posicion en x para la tercera tabla:
    x_position_for_third_table=260
    third_col_widths = [110, 40]
    third_table = Table(third_data_table, colWidths=third_col_widths, rowHeights=14)
    third_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    third_table.setStyle(third_table_style)
    third_table_height = len(third_data_table) * 14
    third_table.wrapOn(c, width, height)
    third_table.drawOn(c, x_position_for_third_table, current_y - third_table_height )

    #PARA VALIDACION DEL VALOR CRT
    peso_total_toneladas=data['dataForm']['pesoNetoCrt']/1000
    flete_pactado= data["dataForm"]["fletePactado"]
    monto_flete = round((peso_total_toneladas * flete_pactado),2)
    flete_base=data["procesado"]["flete_base"]
    estado_crt=""
    if(flete_base <= monto_flete):
        estado_crt="NO SOBREPASA VALOR CRT"
    else:
        estado_crt="SOBREPASA VALOR CRT"
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x_position_for_third_table + 150 +10 , current_y-8,estado_crt)



    # Primera LLave para descuento sacos RMH
    c.setLineWidth(0.5)
    first_x_position_for_key = x_position_for_third_table + 150 +10
    first_key_y_position = current_y - (14 * 3)
    last_key_y_position=first_key_y_position - (14 * 3)
    middle_of_key= (first_key_y_position + last_key_y_position)/2
    inclinacion=2
    c.line(first_x_position_for_key, first_key_y_position-inclinacion, first_x_position_for_key, last_key_y_position+inclinacion)
    c.line(first_x_position_for_key, first_key_y_position-inclinacion, first_x_position_for_key-inclinacion, first_key_y_position)
    c.line(first_x_position_for_key-inclinacion, last_key_y_position , first_x_position_for_key , last_key_y_position+inclinacion)
    c.line(first_x_position_for_key, middle_of_key, first_x_position_for_key+inclinacion,middle_of_key)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(first_x_position_for_key+inclinacion+4,middle_of_key , f"$ {data['procesado']['total_descuento_solo_sacos']:.2f}")

    # Segunda llave para descuento de sacos RMH
    c.setLineWidth(0.5)

    # Coordenadas para dibujar segunda la llave
    key_start_x = first_x_position_for_key+inclinacion+4 + 40
    key_start_y = current_y - 14
    key_end_y = key_start_y - (14 * 5)
    key_middle_y = (key_start_y + key_end_y) / 2
    key_inclination = 2

    # Dibujar la llave
    c.line(key_start_x, key_start_y - key_inclination, key_start_x, key_end_y + key_inclination)
    c.line(key_start_x, key_start_y - key_inclination, key_start_x - key_inclination, key_start_y)
    c.line(key_start_x - key_inclination, key_end_y, key_start_x, key_end_y + key_inclination)
    c.line(key_start_x, key_middle_y, key_start_x + key_inclination, key_middle_y)

    # Texto del descuento
    c.setFont("Helvetica-Bold", 7)
    c.drawString(key_start_x + key_inclination + 4, key_middle_y,
                 f"$ {data['procesado']['aux_descuento']:.2f}")


    # Lista de placas y estado de estiba:
    y_position_for_list=current_y-third_table_height-10
    c.setFont("Helvetica", 6)
    for item in data["procesado"]["pago_estiba_list"]:
        # Crear texto en una línea
        c.drawString(x_position_for_third_table, y_position_for_list, f"{item['placa']} {item['detalle']}")  # Placa y detalle
        c.drawString(x_position_for_third_table + 130, y_position_for_list, f"$ {item['monto_descuento']:.2f}")  # Monto alineado a la derecha
        y_position_for_list -= 10  # Reducir la posición vertical para la próxima línea


    # Coordenadas para dibujar la tercera llave
    tirth_key_start_x = first_x_position_for_key
    tirth_key_start_y = current_y-third_table_height-5
    tirth_key_end_y = y_position_for_list +10
    tirth_key_middle_y = (tirth_key_start_y + tirth_key_end_y) / 2
    tirth_key_inclination = 2
    # Dibujar la tercera llave
    c.line(tirth_key_start_x, tirth_key_start_y - tirth_key_inclination, tirth_key_start_x,
           tirth_key_end_y + tirth_key_inclination)
    c.line(tirth_key_start_x, tirth_key_start_y - tirth_key_inclination, tirth_key_start_x - tirth_key_inclination,
           tirth_key_start_y)
    c.line(tirth_key_start_x - tirth_key_inclination, tirth_key_end_y, tirth_key_start_x,
           tirth_key_end_y + tirth_key_inclination)
    c.line(tirth_key_start_x, tirth_key_middle_y, tirth_key_start_x + tirth_key_inclination, tirth_key_middle_y)
    # Texto del descuento
    c.setFont("Helvetica-Bold", 7)
    c.drawString(tirth_key_start_x + tirth_key_inclination + 4, tirth_key_middle_y-2,
                 f"$ {data['procesado']['total_descuento_estiba']:.2f}")


    # Escribir linea de neto a pagar
    table_total_data = [
        ["TOTAL A PAGAR:", f"${data['procesado']['total_a_pagar']:.2f}"]
    ]
    # Crear la tabla
    table_total = Table(table_total_data, colWidths=[110, 40])  # Anchos de columnas
    # Aplicar estilo a la tabla
    table_total.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.orange),  # Fondo naranja
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),  # Texto en color negro
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alineación izquierda primera columna
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),  # Fuente en negrita
        ('FONTSIZE', (0, 0), (-1, -1), 8),  # Tamaño de la fuente
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), # Alineación derecha segunda columna
    ]))
    altura_tabla_total=len(table_total_data) * 14
    table_total.wrapOn(c, width, height)
    table_total.drawOn(c, x_position_for_third_table, y_position_for_list - altura_tabla_total-20)



    # Data para la tabla #4 (resumen de descuentos)
    new_x_position = 260 + 150 + 150
    fourth_data_table=[
        ["FLETE", f"$ {data["procesado"]["flete_base"]:.2f}"],
        ["Dscto.", f"$ {data["procesado"]["total_dsct"]:.2f}"],
        ["Neto.", f"$ {data["procesado"]["total_a_pagar"]:.2f}"],
    ]
    fourth_col_widths = [30, 50]
    fourth_table = Table(fourth_data_table, colWidths=fourth_col_widths, rowHeights=14)
    fourth_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    fourth_table.setStyle(fourth_table_style)
    fourth_table_height = len(fourth_data_table) * 14
    fourth_table.wrapOn(c, width, height)
    fourth_table.drawOn(c, new_x_position, current_y - fourth_table_height - (14*3))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(new_x_position, current_y - fourth_table_height + 5, "RESUMEN")

    # Data para la tabla #5 (determinacion de costos)
    second_new_x_position = new_x_position + 120
    c.setFont("Helvetica-Bold", 6)
    c.drawString(second_new_x_position, current_y+5, "Determinacion de costo x Kg.")
    fifth_data_table=[
        ["C.P",f"{data["procesado"]["precio_por_tonelada"]:.2f}"],
        ["F.B", f"$ {data["dataForm"]["fletePactado"]:.2f}"],
        ["G.N", f"{data["dataExtra"]["gastosNacionalizacion"]}"],
        ["MF CIA", f"{data["dataExtra"]["margenFinanciero"]}"],
        ["IGV 18%", f"{data["procesado"]["igv"]}"],
        ["PRECIO DES", f"{data["procesado"]["precio_bruto_final"]}"],
        ["COSTO TM", f"{data["procesado"]["precio_por_tonelada_final"]}"],
        ["COSTO Kg", f"{data["procesado"]["precio_por_kg_final"]}"],
    ]
    fifth_col_widths = [50, 40]
    fifth_table = Table(fifth_data_table, colWidths=fifth_col_widths, rowHeights=14)
    fifth_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    fifth_table.setStyle(fifth_table_style)
    fifth_table_height = len(fifth_data_table) * 14
    fifth_table.wrapOn(c, width, height)
    fifth_table.drawOn(c, second_new_x_position, current_y - fifth_table_height)


    # SALTO DE LINEA PARA ESPACIO DE DESCUENTOS
    current_y = current_y - second_table_height - 20

    x_start = 40  # Eje X constante
    line_height = 10  # Interlineado
    # Escribir título
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_start, current_y, "Descuentos:")
    current_y -= line_height + 5  # Reducir Y para el siguiente contenido
    # Cambiar la fuente para los detalles
    c.setFont("Helvetica", 7)
    # Condicionales y datos
    if data["procesado"]["descuento_por_diferencia_peso"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x dif. peso $ {data['procesado']['descuento_por_diferencia_peso']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["descuento_sacos_faltantes"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x sacos falt. $ {data['procesado']['descuento_sacos_faltantes']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["total_descuento_solo_sacos"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x sacos R,H,M. $ {data['procesado']['total_descuento_solo_sacos']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["total_descuento_estiba"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x estibaje $ {data['procesado']['total_descuento_estiba']:.2f}"
        )
        current_y -= line_height

    # Total
    c.setFont("Helvetica-Bold", 8)
    c.drawString(
        x_start,
        current_y - 5,
        f"TOTAL A DESCONTAR:   $ {data['procesado']['total_dsct']:.2f}"
    )





    # Guardar el PDF en el buffer
    c.showPage()
    c.save()

    # Mover el puntero del buffer al inicio para poder leerlo
    buffer.seek(0)

    # Crear la respuesta HTTP con el archivo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_calculo_flete.pdf"'
    response.write(buffer.getvalue())
    buffer.close()

    return response

def generar_reporte_detallado(request, styleSheet=None):
    data_unprocess = json.loads(request.body)
    data = procesar_data_reporte(data_unprocess)
    buffer = io.BytesIO()

    # Crear un archivo PDF
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    c.setTitle(" Reporte cálculo de flete detallado")


    # Obtener las dimensiones de la página
    width, height = landscape(A4)



    # primera linea
    c.setFont("Helvetica", 10)
    current_y = height - 40
    c.drawString(40, current_y, f"{data['procesado']['empresa']}")

    current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.setFont("Helvetica",7)
    c.drawString(width-130, current_y, f"{current_datetime}")

    #segunda linea
    c.setFont("Helvetica-Bold", 10)
    texto = f"{data['dataForm']['producto']}"
    text_width = c.stringWidth(texto, "Helvetica", 12)
    # Calcular la posición X para centrar el texto
    x_position = (width - text_width) / 2 + 20
    # Dibujar el texto centrado
    current_y-=20
    c.drawString(x_position, current_y, texto)

    # tercera linea
    current_y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, current_y, f"CARTA PORTE: {data['dataForm']['cartaPorte']}")



    # CUARTA LINEA DATOS DEL DESPACHO
    ordenes_recojo = data['dataForm']['ordenRecojo']
    ordenes_string = " / ".join([f"{row['oc']['numero_oc']}({row['numeroRecojo']})" for row in ordenes_recojo])
    textos = [
        f"N° DUA: {data['dataForm']['dua']}",
        f"Fec. Num.: {data['procesado']['fecha_numeracion']}",
        f"Factura N°: {data['dataForm']['numFactura']}",
        f"OC: {ordenes_string}",
        f"CANT. {data['procesado']['total_sacos_cargados']} sacos",
        f" {data['dataForm']['pesoNetoCrt']} kg"
    ]
    # Fuente y tamaño
    font_name = "Helvetica"
    font_size = 8
    c.setFont(font_name, font_size)
    # Espacio entre columnas
    margin = 30
    # Posición inicial en Y (mantener fija)
    current_y -= 20
    y_position = current_y
    # Posición inicial en X
    x_position = 40
    # Dibujar todos los textos en una línea tomando en cuenta su tamaño para darle cierto espaciado
    for texto in textos:
        # Calcular el ancho de cada texto
        text_width = c.stringWidth(texto, font_name, font_size)

        # Dibujar el texto
        c.drawString(x_position, y_position, texto)

        # Actualizar la posición X para el siguiente texto
        x_position += text_width + margin

        # Si el texto excede el tamaño de la página en el eje X, detener la creación del contenido
        if x_position > width:
            break



    #QUINTA LINEA DONDE INICIA LA TABLA:
    current_y -= 20
    # Datos iniciales de la tabla #1 (Titulos y subtitulos)
    data_table = [
        # Línea de títulos
        ['FEC. INGRE.', 'EMPRESA DE TRANSP.', 'CARGA', '', '', '', 'DESCARGA', '', '', '', 'DESCUENTOS', '', '', '',
         ''],
        ['', '', 'N°', 'Placa S.', 'Sacos C.', 'Peso S.', 'Placa L.', 'Sacos D.', 'Peso L.', 'Merma', 'S. Falt.',
         'S. Rotos', 'S. Humed.', 'S. Mojad.', 'Estibaje'],
    ]
    # Agregamos datos dinamicamente a la tabla
    styles = getSampleStyleSheet()
    parrafo = Paragraph(f"<para align=center spaceb=3><b>{data['dataForm']['transportista']}</b></para>",
                      styles["BodyText"])
    for i, row in enumerate(data['dataTable']):
        if i == 0:  # Primera fila (datos especiales)
            data_table.append([
                f"{data['procesado']['fecha_numeracion']}",
                parrafo,
                str(row['numero']),
                row['placa'],
                str(row['sacosCargados']),
                str(row['pesoSalida']),
                row['placaLlegada'],
                str(row['sacosDescargados']),
                str(row['pesoLlegada']),
                str(row['merma']),
                str(row['sacosFaltantes']),
                str(row['sacosRotos']),
                str(row['sacosHumedos']),
                str(row['sacosMojados']),
                str(row['pagoEstiba']),
            ])
        else:  # Para el resto de las filas
            data_table.append([
                "",  # Cadena vacía
                "",  # Cadena vacía
                str(row['numero']),
                row['placa'],
                str(row['sacosCargados']),
                str(row['pesoSalida']),
                row['placaLlegada'],
                str(row['sacosDescargados']),
                str(row['pesoLlegada']),
                str(row['merma']),
                str(row['sacosFaltantes']),
                str(row['sacosRotos']),
                str(row['sacosHumedos']),
                str(row['sacosMojados']),
                str(row['pagoEstiba']),
            ])
    # Agregamos
    data_table.append(
        ['', f"Flete x TM: $ {data['dataForm']['fletePactado']:.2f}", f"{data['procesado']['len_tabla']}", 'TOTAL',
         f"{data['procesado']['total_sacos_cargados']}", f"{data['procesado']['suma_peso_salida']}", 'TOTAL',
         f"{data['procesado']['total_sacos_descargados']}", f"{data['procesado']['suma_peso_llegada']}",
         f"{data['procesado']['merma_total']}", f"{data['procesado']['total_sacos_faltantes']}",
         f"{data['procesado']['total_sacos_rotos']}", f"{data['procesado']['total_sacos_humedos']}",
         f"{data['procesado']['total_sacos_mojados']}"])
    # Ancho de columnas
    col_widths = [60, 110, 20, 60, 40, 60, 60, 60, 40, 60, 30, 30, 30, 30, 70]
    # Crear la tabla
    table = Table(data_table, colWidths=col_widths, rowHeights=15)
    color_rosa = Color(red=250 / 255, green=210 / 255, blue=202 / 255)
    color_celeste = Color(red=176 / 255, green=225 / 255, blue=250 / 255)
    numero_filas = len(data_table)
    # Estilos para la tabla
    table_style = TableStyle([
        ('SPAN', (0, 0), (0, 1)),  # Fusionar "FEC. INGRE."
        ('SPAN', (1, 0), (1, 1)),  # Fusionar "EMPRESA DE TRANSP."
        ('SPAN', (2, 0), (5, 0)),  # Fusionar "CARGA"
        ('SPAN', (6, 0), (9, 0)),  # Fusionar "DESCARGA"
        ('SPAN', (10, 0), (14, 0)),  # Fusionar "DESCUENTOS"
        ('SPAN', (0, 2), (0, numero_filas - 1)),  # Fusionar "fecha"
        ('SPAN', (1, 2), (1, numero_filas - 2)),  # Fusionar "nombre empresa transporte"
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centrar todo
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Fondo gris para los títulos
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),  # Fondo gris claro para subtítulos
        ('BACKGROUND', (2, 0), (5, numero_filas), colors.yellowgreen),  # Color "CARGA"
        ('BACKGROUND', (6, 0), (9, numero_filas), color_celeste),  # Color "DESCARGA"
        ('BACKGROUND', (10, 0), (14, numero_filas), color_rosa),  # Fusionar "DESCUENTOS"
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Negrita en títulos
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),  # Negrita en subtítulos

        # ('FONTSIZE', (15, 0), (15, numero_filas - 1), 5),
    ])
    table_style.add('FONTSIZE', (1, 2), (1, numero_filas - 2), 5)
    # Aplicar estilos a la tabla
    table.setStyle(table_style)
    # Calcular la altura total de la tabla
    table_height = len(data_table) * 15 # 20 es la altura de cada fila
    # Calcular la posición de la tabla en la página
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, current_y - table_height )  # Ajustar la posición dependiendo de la cantidad de filas

    current_y= current_y - table_height - 20

    # Data para la tabla #2 (Detalles de pesos)
    second_data_table=[
        ["Faltante peso Sta. Cruz - Desaguadero:",f"{data['procesado']['diferencia_de_peso']:.2f} Kg."],
        ["Merma permitida:",f"{data['dataExtra']['mermaPermitida']:.2f} Kg."],
        ["Desc. diferencia de peso:",f"{data['procesado']['diferencia_peso_por_cobrar']:.2f} Kg."],
        ["Desc. sacos falantes:",f"{data['procesado']['descuento_peso_sacos_faltantes']:.2f} Kg."]
    ]
    second_col_widths=[110,50]
    second_table = Table(second_data_table, colWidths=second_col_widths,rowHeights=14)
    second_table_style=TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Centrar
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    second_table.setStyle(second_table_style)
    second_table_height = len(second_data_table) * 14
    second_table.wrapOn(c, width, height)
    second_table.drawOn(c, 40,current_y - second_table_height )


    #Data para la tabla #3 (Resumen de descuentos)
    third_data_table=[
        ["FLETE",f"$ {data["procesado"]["flete_base"]:.2f}"],
        ["Dscto. por dif. de peso", f"$ {data["procesado"]["descuento_por_diferencia_peso"]:.2f}"],
        ["Dscto. por sacos faltantes", f"$ {data["procesado"]["descuento_sacos_faltantes"]:.2f}"],
        ["Dscto. por sacos rotos", f"$ {data["procesado"]["descuento_sacos_rotos"]:.2f}"],
        ["Dscto. por sacos humedos", f"$ {data["procesado"]["descuento_sacos_humedos"]:.2f}"],
        ["Dscto. por sacos mojados", f"$ {data["procesado"]["descuento_sacos_mojados"]:.2f}"],
        ["FLETE TOTAL", f"$ {data["procesado"]["total_luego_dsctos_sacos"]:.2f}"],
    ]
    #posicion en x para la tercera tabla:
    x_position_for_third_table=260
    third_col_widths = [110, 40]
    third_table = Table(third_data_table, colWidths=third_col_widths, rowHeights=14)
    third_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    third_table.setStyle(third_table_style)
    third_table_height = len(third_data_table) * 14
    third_table.wrapOn(c, width, height)
    third_table.drawOn(c, x_position_for_third_table, current_y - third_table_height )

    #PARA VALIDACION DEL VALOR CRT
    peso_total_toneladas=data['dataForm']['pesoNetoCrt']/1000
    flete_pactado= data["dataForm"]["fletePactado"]
    monto_flete = round((peso_total_toneladas * flete_pactado),2)
    flete_base=data["procesado"]["flete_base"]
    estado_crt=""
    if(flete_base <= monto_flete):
        estado_crt="NO SOBREPASA VALOR CRT"
    else:
        estado_crt="SOBREPASA VALOR CRT"
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x_position_for_third_table + 150 +10 , current_y-8,estado_crt)



    # Primera LLave para descuento sacos RMH
    c.setLineWidth(0.5)
    first_x_position_for_key = x_position_for_third_table + 150 +10
    first_key_y_position = current_y - (14 * 3)
    last_key_y_position=first_key_y_position - (14 * 3)
    middle_of_key= (first_key_y_position + last_key_y_position)/2
    inclinacion=2
    c.line(first_x_position_for_key, first_key_y_position-inclinacion, first_x_position_for_key, last_key_y_position+inclinacion)
    c.line(first_x_position_for_key, first_key_y_position-inclinacion, first_x_position_for_key-inclinacion, first_key_y_position)
    c.line(first_x_position_for_key-inclinacion, last_key_y_position , first_x_position_for_key , last_key_y_position+inclinacion)
    c.line(first_x_position_for_key, middle_of_key, first_x_position_for_key+inclinacion,middle_of_key)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(first_x_position_for_key+inclinacion+4,middle_of_key , f"$ {data['procesado']['total_descuento_solo_sacos']:.2f}")

    # Segunda llave para descuento de sacos RMH
    c.setLineWidth(0.5)

    # Coordenadas para dibujar segunda la llave
    key_start_x = first_x_position_for_key+inclinacion+4 + 40
    key_start_y = current_y - 14
    key_end_y = key_start_y - (14 * 5)
    key_middle_y = (key_start_y + key_end_y) / 2
    key_inclination = 2

    # Dibujar la llave
    c.line(key_start_x, key_start_y - key_inclination, key_start_x, key_end_y + key_inclination)
    c.line(key_start_x, key_start_y - key_inclination, key_start_x - key_inclination, key_start_y)
    c.line(key_start_x - key_inclination, key_end_y, key_start_x, key_end_y + key_inclination)
    c.line(key_start_x, key_middle_y, key_start_x + key_inclination, key_middle_y)

    # Texto del descuento
    c.setFont("Helvetica-Bold", 7)
    c.drawString(key_start_x + key_inclination + 4, key_middle_y,
                 f"$ {data['procesado']['aux_descuento']:.2f}")


    # Lista de placas y estado de estiba:
    y_position_for_list=current_y-third_table_height-10
    c.setFont("Helvetica", 6)
    for item in data["procesado"]["pago_estiba_list"]:
        # Crear texto en una línea
        c.drawString(x_position_for_third_table, y_position_for_list, f"{item['placa']} {item['detalle']}")  # Placa y detalle
        c.drawString(x_position_for_third_table + 130, y_position_for_list, f"$ {item['monto_descuento']:.2f}")  # Monto alineado a la derecha
        y_position_for_list -= 10  # Reducir la posición vertical para la próxima línea


    # Coordenadas para dibujar la tercera llave
    tirth_key_start_x = first_x_position_for_key
    tirth_key_start_y = current_y-third_table_height-5
    tirth_key_end_y = y_position_for_list +10
    tirth_key_middle_y = (tirth_key_start_y + tirth_key_end_y) / 2
    tirth_key_inclination = 2
    # Dibujar la tercera llave
    c.line(tirth_key_start_x, tirth_key_start_y - tirth_key_inclination, tirth_key_start_x,
           tirth_key_end_y + tirth_key_inclination)
    c.line(tirth_key_start_x, tirth_key_start_y - tirth_key_inclination, tirth_key_start_x - tirth_key_inclination,
           tirth_key_start_y)
    c.line(tirth_key_start_x - tirth_key_inclination, tirth_key_end_y, tirth_key_start_x,
           tirth_key_end_y + tirth_key_inclination)
    c.line(tirth_key_start_x, tirth_key_middle_y, tirth_key_start_x + tirth_key_inclination, tirth_key_middle_y)
    # Texto del descuento
    c.setFont("Helvetica-Bold", 7)
    c.drawString(tirth_key_start_x + tirth_key_inclination + 4, tirth_key_middle_y-2,
                 f"$ {data['procesado']['total_descuento_estiba']:.2f}")


    # Escribir linea de neto a pagar
    table_total_data = [
        ["TOTAL A PAGAR:", f"${data['procesado']['total_a_pagar']:.2f}"]
    ]
    # Crear la tabla
    table_total = Table(table_total_data, colWidths=[110, 40])  # Anchos de columnas
    # Aplicar estilo a la tabla
    table_total.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.orange),  # Fondo naranja
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),  # Texto en color negro
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alineación izquierda primera columna
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),  # Fuente en negrita
        ('FONTSIZE', (0, 0), (-1, -1), 8),  # Tamaño de la fuente
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), # Alineación derecha segunda columna
    ]))
    altura_tabla_total=len(table_total_data) * 14
    table_total.wrapOn(c, width, height)
    table_total.drawOn(c, x_position_for_third_table, y_position_for_list - altura_tabla_total-20)


    # Escribir linea de comprobacion
    total_a_pagar=data["procesado"]["total_a_pagar"]
    total_desctos=data["procesado"]["total_dsct"]
    monto_final=total_a_pagar+total_desctos
    diferencia= round((monto_final - flete_base),2)
    table_total_data = [
        ["COMPROBACIÓN", f"$ {monto_final:.2f}",f"$ {diferencia}"]
    ]
    # Crear la tabla
    table_total = Table(table_total_data, colWidths=[80, 60,60])  # Anchos de columnas
    # Aplicar estilo a la tabla
    table_total.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.orange),  # Fondo naranja
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),  # Texto en color negro
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Alineación izquierda primera columna
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),  # Fuente en negrita
        ('FONTSIZE', (0, 0), (-1, -1), 8),  # Tamaño de la fuente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
    ]))
    altura_tabla_total = len(table_total_data) * 14
    table_total.wrapOn(c, width, height)
    table_total.drawOn(c, 40, y_position_for_list - altura_tabla_total - 70)


    # Data para la tabla #4 (resumen de descuentos)
    new_x_position = 260 + 150 + 150
    fourth_data_table=[
        ["FLETE", f"$ {data["procesado"]["flete_base"]:.2f}"],
        ["Dscto.", f"$ {data["procesado"]["total_dsct"]:.2f}"],
        ["Neto.", f"$ {data["procesado"]["total_a_pagar"]:.2f}"],
    ]
    fourth_col_widths = [30, 50]
    fourth_table = Table(fourth_data_table, colWidths=fourth_col_widths, rowHeights=14)
    fourth_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    fourth_table.setStyle(fourth_table_style)
    fourth_table_height = len(fourth_data_table) * 14
    fourth_table.wrapOn(c, width, height)
    fourth_table.drawOn(c, new_x_position, current_y - fourth_table_height - (14*3))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(new_x_position, current_y - fourth_table_height + 5, "RESUMEN")

    # Data para la tabla #5 (determinacion de costos)
    second_new_x_position = new_x_position + 120
    c.setFont("Helvetica-Bold", 6)
    c.drawString(second_new_x_position, current_y+5, "Determinacion de costo x Kg.")
    fifth_data_table=[
        ["C.P",f"{data["procesado"]["precio_por_tonelada"]:.2f}"],
        ["F.B", f"$ {data["dataForm"]["fletePactado"]:.2f}"],
        ["G.N", f"{data["dataExtra"]["gastosNacionalizacion"]}"],
        ["MF CIA", f"{data["dataExtra"]["margenFinanciero"]}"],
        ["IGV 18%", f"{data["procesado"]["igv"]}"],
        ["PRECIO DES", f"{data["procesado"]["precio_bruto_final"]}"],
        ["COSTO TM", f"{data["procesado"]["precio_por_tonelada_final"]}"],
        ["COSTO Kg", f"{data["procesado"]["precio_por_kg_final"]}"],
    ]
    fifth_col_widths = [50, 40]
    fifth_table = Table(fifth_data_table, colWidths=fifth_col_widths, rowHeights=14)
    fifth_table_style = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alinear toda la tabla a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrar verticalmente
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Añadir cuadrícula
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinear la segunda columna a la derecha
    ])
    fifth_table.setStyle(fifth_table_style)
    fifth_table_height = len(fifth_data_table) * 14
    fifth_table.wrapOn(c, width, height)
    fifth_table.drawOn(c, second_new_x_position, current_y - fifth_table_height)


    # SALTO DE LINEA PARA ESPACIO DE DESCUENTOS
    current_y = current_y - second_table_height - 20
    x_start = 40  # Eje X constante
    line_height = 10  # Interlineado
    # Escribir título
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_start, current_y, "Descuentos:")
    current_y -= line_height + 5  # Reducir Y para el siguiente contenido
    # Cambiar la fuente para los detalles
    c.setFont("Helvetica", 7)
    # Condicionales y datos
    if data["procesado"]["descuento_por_diferencia_peso"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x dif. peso $ {data['procesado']['descuento_por_diferencia_peso']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["descuento_sacos_faltantes"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x sacos falt. $ {data['procesado']['descuento_sacos_faltantes']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["total_descuento_solo_sacos"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x sacos R,H,M. $ {data['procesado']['total_descuento_solo_sacos']:.2f}"
        )
        current_y -= line_height

    if data["procesado"]["total_descuento_estiba"] > 0:
        c.drawString(
            x_start,
            current_y,
            f"B/V 004-:        dscto. x estibaje $ {data['procesado']['total_descuento_estiba']:.2f}"
        )
        current_y -= line_height

    # Total
    c.setFont("Helvetica-Bold", 8)
    c.drawString(
        x_start,
        current_y - 5,
        f"TOTAL A DESCONTAR:   $ {data['procesado']['total_dsct']:.2f}"
    )





    # Guardar el PDF en el buffer
    c.showPage()
    c.save()

    # Mover el puntero del buffer al inicio para poder leerlo
    buffer.seek(0)

    # Crear la respuesta HTTP con el archivo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_calculo_flete.pdf"'
    response.write(buffer.getvalue())
    buffer.close()

    return response

def registrar_despacho(request):
    if request.method == 'POST':
        try:
            # Parsear el JSON de la request
            data = json.loads(request.body)

            # Procesar `dataForm`
            data_form = data.get('dataForm', {})
            empresa, _ = Empresa.objects.get_or_create(nombre_empresa=data_form.get('empresa'))
            providers, _ = ProveedorTransporte.objects.get_or_create(nombre_proveedor=data_form.get('proveedor'))
            transportista, _ = Transportista.objects.get_or_create(nombre_transportista=data_form.get('transportista'))
            fecha_llegada=
            # Iniciar transacción
            with transaction.atomic():
                # Crear el Despacho
                despacho = Despacho.objects.create(
                    proveedor=providers,
                    dua=data_form.get('dua', ''),
                    fecha_numeracion=data_form.get('fechaNumeracion'),
                    carta_porte=data_form.get('cartaPorte', None),
                    num_factura=data_form.get('numFactura', ''),
                    transportista=transportista,
                    flete_pactado=data_form.get('fletePactado', 0.0),
                    peso_neto_crt=data_form.get('pesoNetoCrt', 0.0)
                )

                # Procesar cada orden de compra y su número de recojo
                for orden_recojo in data_form.get('ordenRecojo', []):
                    oc_data = orden_recojo.get('oc', {})
                    numero_recojo = orden_recojo.get('numeroRecojo')

                    # Validar datos de `oc_data`
                    if not all(k in oc_data for k in ['codigo_producto', 'producto', 'proveedor', 'numero_oc', 'precio_unitario', 'cantidad']):
                        raise ValueError("Faltan datos necesarios en `oc`.")

                    # Crear o recuperar el producto
                    producto, _ = Producto.objects.get_or_create(
                        codigo_producto=oc_data['codigo_producto'],
                        nombre_producto=oc_data['producto'],
                        proveedor_marca=oc_data['proveedor']
                    )

                    # Crear o recuperar la OrdenCompra
                    orden_compra, _ = OrdenCompra.objects.get_or_create(
                        empresa=empresa,
                        numero_oc=oc_data['numero_oc'],
                        producto=producto,
                        defaults={
                            'precio_producto': oc_data['precio_unitario'],
                            'cantidad': oc_data['cantidad']
                        }
                    )

                    # Verificar si ya existe la combinación de OC y número de recojo
                    if OrdenCompraDespacho.objects.filter(
                        orden_compra=orden_compra,
                        numero_recojo=numero_recojo
                    ).exists():
                        return JsonResponse(
                            {
                                'status': 'error',
                                'message': f'La OC "{orden_compra.numero_oc}" con número de recojo "{numero_recojo}" ya existe.'
                            },
                            status=400
                        )

                    # Crear la relación OrdenCompraDespacho
                    OrdenCompraDespacho.objects.create(
                        despacho=despacho,
                        orden_compra=orden_compra,
                        cantidad_asignada=oc_data['cantidad'],
                        numero_recojo=numero_recojo
                    )

                # Procesar `dataTable` para DetalleDespacho
                for item in data.get('dataTable', []):
                    DetalleDespacho.objects.create(
                        despacho=despacho,
                        placa_salida=item.get('placa', ''),
                        sacos_cargados=item.get('sacosCargados', 0),
                        peso_salida=item.get('pesoSalida', 0.0),
                        placa_llegada=item.get('placaLlegada', ''),
                        sacos_descargados=item.get('sacosDescargados', 0),
                        peso_llegada=item.get('pesoLlegada', 0.0),
                        merma=item.get('merma', 0),
                        sacos_faltantes=item.get('sacosFaltantes', 0),
                        sacos_rotos=item.get('sacosRotos', 0),
                        sacos_humedos=item.get('sacosHumedos', 0),
                        sacos_mojados=item.get('sacosMojados', 0),
                        pago_estiba=item.get('pagoEstiba', 0.0),
                        cant_desc=item.get('cantDesc', 0)
                    )

                # Procesar `dataExtraForm` para ConfiguracionDespacho
                data_extra_form = data.get('dataExtraForm', {})
                ConfiguracionDespacho.objects.create(
                    despacho=despacho,
                    merma_permitida=data_extra_form.get('mermaPermitida', 0.0),
                    precio_prod=data_extra_form.get('precioProd', 0.0),
                    gastos_nacionalizacion=data_extra_form.get('gastosNacionalizacion', 0.0),
                    margen_financiero=data_extra_form.get('margenFinanciero', 0.0),
                    precio_sacos_rotos=data_extra_form.get('precioSacosRotos', 0.0),
                    precio_sacos_humedos=data_extra_form.get('precioSacosHumedos', 0.0),
                    precio_sacos_mojados=data_extra_form.get('precioSacosMojados', 0.0),
                    tipo_cambio_desc_ext=data_extra_form.get('tipoCambioDescExt', 0.0)
                )

            return JsonResponse({'status': 'success', 'message': 'Registro realizado correctamente'}, status=201)


        except IntegrityError as e:

            return JsonResponse({

                'status': 'error',

                'message': f'Error de integridad: {str(e)}. Asegúrese de que los datos sean correctos.'

            }, status=400)
        except ValueError as ve:
            return JsonResponse({'status': 'error', 'message': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)








