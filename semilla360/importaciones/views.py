import math
from datetime import datetime

from django.db import connections
from reportlab.lib.pagesizes import landscape, letter
from io import BytesIO
from reportlab.pdfgen import canvas
from .models import (OrdenCompraStarsoft, Proveedor, Empresa, OrdenCompra, Producto, Proveedor_transporte, Transportista,
    Despacho, DetalleDespacho, ConfiguracionDespacho)
from .forms import BaseDatosForm
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, HttpResponse
from rest_framework.decorators import api_view
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber
import json
from .utils import calcular_monto_descuento_estiba,renderizar_template,convertir_html_a_pdf,procesar_data_reporte
import os
import tempfile

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
                    'CNUMERO': row[0],  # Asegúrate de que el índice coincida con el esquema de tu tabla
                    'CDESARTIC': row[1],  # Este es solo un ejemplo, ajusta según las columnas
                    'CCODARTIC': row[2],
                    'NCANTIDAD': row[3],
                    'CUNIDAD': row[4],
                    'NPREUNITA': row[5],
                    'NTOTVENT': row[6],
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

def registrar_despacho(request):
    if request.method == 'POST':
        try:
            # Parsear el JSON de la request
            data = json.loads(request.body)

            # Procesar `dataForm`
            data_form = data['dataForm']
            empresa, _ = Empresa.objects.get_or_create(nombre_empresa=data_form['empresa'])
            producto, _ = Producto.objects.get_or_create(
                nombre_producto=data_form['producto'],
                precio_producto=data_form['precioProducto']
            )
            providers, _ = Proveedor_transporte.objects.get_or_create(nombre_proveedor=data_form['proveedor'])
            transportista, _ = Transportista.objects.get_or_create(nombre_transportista=data_form['transportista'])

            # Crear despacho
            despacho = Despacho.objects.create(
                producto=producto,
                proveedor=providers,
                dua=data_form['dua'],
                num_recojo=data_form.get('numRecojo'),
                fecha_numeracion=data_form['fechaNumeracion'],
                carta_porte=data_form.get('cartaPorte'),
                num_factura=data_form['numFactura'],
                transportista=transportista,
                flete_pactado=data_form['fletePactado'],
                peso_neto_crt=data_form['pesoNetoCrt']
            )

            # Vincular órdenes de compra al despacho después de crearlo
            for numero_oc in data_form['oc']:
                orden_compra, _ = OrdenCompra.objects.get_or_create(
                    empresa=empresa,
                    numero_oc=numero_oc
                )
                despacho.ordenes_compra.add(orden_compra)

                # Procesar `dataTable` para DetalleDespacho
            for item in data['dataTable']:
                DetalleDespacho.objects.create(
                    despacho=despacho,
                    placa_salida=item['placa'],
                    sacos_cargados=item['sacosCargados'],
                    peso_salida=item['pesoSalida'],
                    placa_llegada=item['placaLlegada'],
                    sacos_descargados=item['sacosDescargados'],
                    peso_llegada=item['pesoLlegada'],
                    merma=item['merma'],
                    sacos_faltantes=item['sacosFaltantes'],
                    sacos_rotos=item['sacosRotos'],
                    sacos_humedos=item['sacosHumedos'],
                    sacos_mojados=item['sacosMojados'],
                    pago_estiba=item['pagoEstiba'],
                    cant_desc=item['cantDesc']
                )

            # Procesar `dataExtraForm` para ConfiguracionDespacho
            data_extra_form = data['dataExtraForm']
            ConfiguracionDespacho.objects.create(
                despacho=despacho,
                merma_permitida=data_extra_form['mermaPermitida'],
                precio_prod=data_extra_form['precioProd'],
                gastos_nacionalizacion=data_extra_form['gastosNacionalizacion'],
                margen_financiero=data_extra_form['margenFinanciero'],
                precio_sacos_rotos=data_extra_form['precioSacosRotos'],
                precio_sacos_humedos=data_extra_form['precioSacosHumedos'],
                precio_sacos_mojados=data_extra_form['precioSacosMojados'],
                tipo_cambio_desc_ext=data_extra_form['tipoCambioDescExt']
            )

            return JsonResponse({'status': 'success','message': 'Registro realizado correctamente'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

